# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


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

    # def _generate_price_difference_vals(self, layers):
    #     self = self.with_context(
    #         valuation_area=self._get_valuation_area(),
    #         account_modifier=self._get_account_modifier(),
    #         transaction_key="stock_receipt_price_difference",
    #     )
    #
    #     return super()._generate_price_difference_vals(layers)
