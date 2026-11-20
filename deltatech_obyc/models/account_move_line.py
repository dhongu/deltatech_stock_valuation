# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_account_modifier(self):
        account_modifier = self.env["account.modifier"]
        return account_modifier

    def _get_standard_product_account(self):
        """Contul de venit/cheltuială din produs sau din categorie, mapat prin poziția fiscală.

        Cu clasă de evaluare, `_get_product_accounts` golește conturile standard (OBYC le
        înlocuiește), așa că, atunci când nu există nicio regulă, contul se citește direct.
        """
        self.ensure_one()
        product = self.product_id.with_company(self.company_id)
        if self.move_id.is_sale_document(include_receipts=True):
            account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        else:
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
        if account and self.move_id.fiscal_position_id:
            account = self.move_id.fiscal_position_id.map_account(account)
        return account

    def _compute_account_id(self):
        self = self.with_context(transaction_key="skip")
        res = super()._compute_account_id()

        product_lines = self.filtered(lambda line: line.display_type == "product" and line.move_id.is_invoice(True))
        for line in product_lines:
            if not line.product_id._get_valuation_class():
                continue

            # VA-006: doar produsele stocabile cer arie de evaluare (ca în
            # `_is_valuation_area_required`). Un serviciu sau un consumabil care
            # moștenește clasa din categorie nu oprește factura când aria lipsește.
            is_storable = line.product_id.is_storable
            valuation_area = line._get_valuation_area(raise_if_not_found=is_storable)

            transaction_key = False

            if line.move_id.is_sale_document(include_receipts=True):
                transaction_key = "stock_income"
            elif line.move_id.is_purchase_document(include_receipts=True):
                transaction_key = "stock_receipt"  # In SAP is WRX

            account_modifier = line._get_account_modifier()

            if not is_storable and not valuation_area and line.company_id.use_valuation_area:
                # Fără arie, nestocabilul folosește regula fără arie, dacă există;
                # altfel primește contul standard al produsului sau al categoriei.
                rule = self.env["product.account.determination"].search(
                    [
                        ("transaction_key", "=", transaction_key),
                        ("account_modifier_id", "=", account_modifier.id),
                        ("valuation_class_id", "=", line.product_id._get_valuation_class().id),
                        ("valuation_area_id", "=", False),
                        ("company_id", "=", line.company_id.id),
                    ],
                    limit=1,
                )
                if not rule:
                    standard_account = line._get_standard_product_account()
                    if standard_account:
                        line.account_id = standard_account
                    continue
            else:
                _get_rule_account = self.env["product.account.determination"]._get_rule_account
                rule = _get_rule_account(
                    valuation_area=valuation_area,
                    valuation_class=line.product_id._get_valuation_class(),
                    transaction_key=transaction_key,
                    account_modifier=account_modifier,
                    company=line.company_id,
                )
            # contul se alege după tipul documentului, nu după debit/credit: la creare
            # compute-ul rulează înainte ca linia să aibă sold. Nota de credit folosește
            # același cont ca factura.
            if transaction_key == "stock_income":
                account = rule.acc_dest_id
            else:
                account = rule.acc_src_id
            line.account_id = account or rule.acc_valuation_id

            line.valuation_area_id = valuation_area

        return res

    # ------------------------------------------------------------------
    # OBYC-014: corecția stocului la factura cu diferență de preț sau de curs
    # ------------------------------------------------------------------
    def _obyc_get_price_difference_data(self):
        """Diferența dintre factură și recepție pentru linia facturii de furnizor.

        Întoarce `False` când nu e nimic de corectat (produs fără OBYC, nestocabil, fără
        recepție făcută sau diferență nulă), altfel un dicționar cu:
        - `receipts`: mișcările de recepție ale liniei de comandă;
        - `stock_amount`: partea diferenței de preț care rămâne în stoc;
        - `expense_amount`: partea diferenței de preț aferentă cantității deja ieșite;
        - `fx_amount`: diferența de curs (pozitivă = pierdere), toate în moneda companiei."""
        self.ensure_one()
        product = self.product_id
        purchase_line = self.purchase_line_id
        if not purchase_line or not product.is_storable or not product._get_valuation_class():
            return False
        company = self.company_id
        currency = company.currency_id
        receipts = purchase_line.move_ids.filtered(
            lambda m: m.state == "done" and m.is_in and m.product_id == product and m.value
        )
        if not receipts:
            return False  # fără recepție, valoarea mișcării se ia din factură (core)
        uom = product.uom_id
        billed_qty = self.product_uom_id._compute_quantity(self.quantity, uom)
        # cantitatea recepționată și încă nefacturată, la valoarea de la recepție
        previous = purchase_line.invoice_lines.filtered(
            lambda aml: aml.move_id.state == "posted" and aml.move_id.move_type == "in_invoice" and aml != self
        )
        previous_qty = sum(aml.product_uom_id._compute_quantity(aml.quantity, uom) for aml in previous)
        received_qty = sum(receipts.mapped(lambda m: m._get_valued_qty()))
        qty = min(billed_qty, max(received_qty - previous_qty, 0.0))
        if float_is_zero(qty, precision_rounding=uom.rounding):
            return False
        order = purchase_line.order_id
        conversion_date = min(receipts.mapped("date")).date()
        received_unit = purchase_line.with_context(conversion_date=conversion_date)._get_stock_move_price_unit()
        invoiced_value = currency.round(self.balance * qty / billed_qty)
        total_diff = currency.round(invoiced_value - qty * received_unit)
        if currency.is_zero(total_diff):
            return False
        price_diff = total_diff
        if order.currency_id == self.currency_id and self.currency_id != currency:
            rate = order.currency_id._get_conversion_rate(order.currency_id, currency, company, conversion_date)
            order_unit_doc = received_unit / rate
            invoiced_unit_doc = self.price_subtotal / billed_qty
            price_diff = currency.round(qty * (invoiced_unit_doc - order_unit_doc) * rate)
        fx_amount = currency.round(total_diff - price_diff)
        in_stock_qty = min(qty, max(product.with_company(company).qty_available, 0.0))
        stock_amount = currency.round(price_diff * in_stock_qty / qty)
        return {
            "receipts": receipts,
            "price_diff": price_diff,
            "stock_amount": stock_amount,
            "expense_amount": currency.round(price_diff - stock_amount),
            "fx_amount": fx_amount,
        }

    def _obyc_price_difference_rule(self, transaction_key, fallback_key=None):
        """Regula OBYC a liniei pentru cheia dată; la lipsă, cea a cheii de rezervă."""
        self.ensure_one()
        determination = self.env["product.account.determination"]
        valuation_class = self.product_id._get_valuation_class()
        valuation_area = self.valuation_area_id or self._get_valuation_area(raise_if_not_found=False)
        modifier = self._get_account_modifier()
        for key in (transaction_key, fallback_key):
            if not key:
                continue
            rule = determination.search(
                [
                    ("transaction_key", "=", key),
                    ("account_modifier_id", "=", modifier.id),
                    ("valuation_class_id", "=", valuation_class.id),
                    ("valuation_area_id", "=", valuation_area.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if rule:
                return rule
        return determination._get_rule_account(
            valuation_area=valuation_area,
            valuation_class=valuation_class,
            transaction_key=fallback_key or transaction_key,
            account_modifier=modifier,
            company=self.company_id,
        )

    def _obyc_price_difference_lines_vals(self, data):
        """Liniile de corecție (balanță în moneda companiei, cu semn)."""
        self.ensure_one()
        company = self.company_id
        currency = company.currency_id
        area = self.valuation_area_id
        entries = []  # (cont, balanță)
        price_diff = data["price_diff"]
        if not currency.is_zero(price_diff):
            rule = self._obyc_price_difference_rule("stock_receipt_price_difference", "stock_receipt")
            entries += [(rule.acc_valuation_id, price_diff), (rule.acc_src_id, -price_diff)]
            if not currency.is_zero(data["expense_amount"]):
                # cantitatea ieșită deja: diferența trece din stoc pe cheltuiala livrării
                expense_rule = self._obyc_price_difference_rule("stock_delivery")
                entries += [
                    (expense_rule.acc_dest_id, data["expense_amount"]),
                    (rule.acc_valuation_id, -data["expense_amount"]),
                ]
        fx_amount = data["fx_amount"]
        if not currency.is_zero(fx_amount):
            rule = self._obyc_price_difference_rule("stock_receipt")
            fx_account = (
                company.expense_currency_exchange_account_id
                if fx_amount > 0
                else company.income_currency_exchange_account_id
            )
            if not fx_account:
                raise UserError(
                    self.env._(
                        "Set the exchange difference accounts of the company %(company)s to post the invoice.",
                        company=company.display_name,
                    )
                )
            entries += [(fx_account, fx_amount), (rule.acc_src_id, -fx_amount)]
        return [
            {
                "name": self.env._("Price difference: %(name)s", name=(self.name or self.product_id.display_name))[:64],
                "move_id": self.move_id.id,
                "partner_id": self.move_id.commercial_partner_id.id,
                "product_id": self.product_id.id,
                "product_uom_id": self.product_uom_id.id,
                "quantity": 0.0,
                "currency_id": currency.id,
                "amount_currency": balance,
                "balance": balance,
                "account_id": account.id,
                "analytic_distribution": self.analytic_distribution,
                "valuation_area_id": area.id,
                "display_type": "cogs",
                "tax_ids": [],
                "cogs_origin_id": self.id,
            }
            for account, balance in entries
        ]
