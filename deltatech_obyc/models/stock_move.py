import logging

from odoo import Command, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    # def _get_accounting_data_for_valuation(self):
    #     if not self.product_id.valuation_class_id:
    #         return super()._get_accounting_data_for_valuation()
    #
    #     valuation_area = self._get_valuation_area()
    #
    #     journal_id = valuation_area.stock_journal_id.id
    #     if not journal_id:
    #         raise UserError(_("Stock journal is not defined for the valuation area"))
    #
    #     picking_type = self.picking_type_id
    #     transaction_key = self._compute_transaction_key()
    #     account_modifier = self.env["account.modifier"]
    #     if picking_type:
    #         account_modifier = picking_type.account_modifier_id
    #
    #     _get_rule_account = self.env["product.account.determination"]._get_rule_account
    #
    #     rule = _get_rule_account(
    #         valuation_area=valuation_area,
    #         valuation_class=self.product_id.valuation_class_id,
    #         transaction_key=transaction_key,
    #         account_modifier=account_modifier,
    #         company=self.company_id,
    #     )
    #     acc_src = rule.acc_src_id.id
    #     acc_dest = rule.acc_dest_id.id
    #     acc_valuation = rule.acc_valuation_id.id
    #
    #     return journal_id, acc_src, acc_dest, acc_valuation

    # def _prepare_account_move_vals(
    #     self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost
    # ):
    #     self.ensure_one()
    #     if credit_account_id == debit_account_id:
    #         return False
    #     vals = super()._prepare_account_move_vals(
    #         credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost
    #     )
    #     if self.company_id.account_storno and self.origin_returned_move_id:
    #         vals["is_storno"] = True
    #     return vals

    # def _account_entry_move(self, qty, description, svl_id, cost):
    #     if not qty:
    #         self = self.with_context(price_difference=True)
    #     am_vals_list = super()._account_entry_move(qty, description, svl_id, cost)
    #     for am_vals in am_vals_list:
    #         if not am_vals:
    #             am_vals_list.remove(am_vals)
    #
    #     return am_vals_list

    def _set_value(self, correction_quantity=None):
        """Completează valoarea mișcărilor dropship pentru produsele OBYC.

        Core (`stock_account._set_value`) include mișcările dropship în
        filtrul `is_in or is_dropship`, dar atribuie `move.value` doar când
        `is_in` e adevărat. Fără acest fix, `_get_account_move_line_vals()`
        de mai jos ar folosi `self.value == 0`, iar nota contabilă OBYC
        generată imediat după (tot în `_action_done()`) ar fi postată cu
        debit=0/credit=0 — o notă aparent înregistrată, dar fără valoare.
        """
        res = super()._set_value(correction_quantity=correction_quantity)
        obyc_dropship_moves = self.filtered(lambda m: m.product_id.valuation_class_id and m.is_dropship and not m.value)
        for move in obyc_dropship_moves:
            move.value = move.sudo()._get_value()
        return res

    def _compute_transaction_key(self):
        source_usage = self.location_id.usage
        dest_usage = self.location_dest_id.usage

        match source_usage, dest_usage:
            # Purchase transactions
            case "supplier", "internal":
                tr_key = "stock_receipt"  # Receipt from supplier
            case "supplier", "transit":
                tr_key = "stock_receipt"  # Receipt from supplier
            case "internal", "supplier":
                tr_key = "return_to_supplier"  # Return to supplier
            case "transit", "supplier":
                tr_key = "return_to_supplier"  # Return to supplier

            # Sale transactions
            case "internal", "customer":
                tr_key = "stock_delivery"  # Delivery to customer
            case "customer", "internal":
                tr_key = "return_from_customer"  # Return from customer
            case "supplier", "customer":
                tr_key = "dropship"  # Drop shipment from supplier to customer
            case "customer", "supplier":
                tr_key = "dropship_return"  # Return from customer to supplier (if applicable)

            # Internal transfers
            case "internal", "internal":
                tr_key = "internal_transfer"
            case "internal", "transit":
                tr_key = "internal_transfer_out"
            case "transit", "internal":
                tr_key = "internal_transfer_in"

            # Inventory adjustments
            case "internal", "inventory":
                tr_key = "inventory_adjustment_plus"
            case "inventory", "internal":
                tr_key = "inventory_adjustment_minus"

            # Production transactions
            case "internal", "production":
                tr_key = "production_issue"  # Issue to production
            case "production", "internal":
                tr_key = "production_receipt"  # Receipt from production
            case _:
                tr_key = False

        if not tr_key:
            raise UserError(
                self.env._(
                    "Transaction key could not be determined for the move from {source_usage} to {dest_usage}.",
                    source_usage=source_usage,
                    dest_usage=dest_usage,
                )
            )
        if self.env.context.get("price_difference"):
            # If the context indicates a price difference, we use a specific transaction key
            tr_key = "price_difference"
        return tr_key

    def _get_rule_account(self):
        self.ensure_one()
        if not self.product_id.valuation_class_id:
            return self.env["product.account.determination"]
        transaction_key = self._compute_transaction_key()
        account_modifier = self.env["account.modifier"]
        valuation_area = self._get_valuation_area()
        if self.picking_type_id:
            account_modifier = self.picking_type_id.account_modifier_id

        _get_rule_account = self.env["product.account.determination"]._get_rule_account

        rule = _get_rule_account(
            valuation_area=valuation_area,
            valuation_class=self.product_id.valuation_class_id,
            transaction_key=transaction_key,
            account_modifier=account_modifier,
            company=self.company_id,
        )

        return rule

    def _should_create_account_move(self):
        if not self.product_id.valuation_class_id:
            return super()._should_create_account_move()

        rule = self._get_rule_account()
        if not rule.acc_src_id and not rule.acc_dest_id and not rule.acc_valuation_id:
            should = False
        else:
            should = True
        return should

    def _is_storno_return(self):
        """Retururile se înregistrează în roșu (storno) când compania are activată
        contabilitatea storno: aceleași conturi ca tranzacția originală, sume negative."""
        self.ensure_one()
        return bool(self.company_id.account_storno and self.origin_returned_move_id)

    def _get_account_move_line_vals(self):
        if not self.product_id.valuation_class_id:
            vals_list = super()._get_account_move_line_vals()
        else:
            rule = self._get_rule_account()

            if rule.acc_src_id:
                debit_acc = rule.acc_valuation_id
                credit_acc = rule.acc_src_id
            else:
                debit_acc = rule.acc_dest_id
                credit_acc = rule.acc_valuation_id
            # cantitatea (SEMNATĂ: negativă pe credit, pozitivă pe debit) și UoM sunt
            # necesare evaluării (deltatech_stock_valuation); aria de evaluare se
            # completează prin compute-ul de pe account.move.line
            quantity = self._get_valued_qty()
            vals_list = [
                {
                    "account_id": credit_acc.id,
                    "name": self.reference,
                    "debit": 0,
                    "credit": self.value,
                    "product_id": self.product_id.id,
                    "quantity": -quantity,
                    "product_uom_id": self.product_id.uom_id.id,
                },
                {
                    "account_id": debit_acc.id,
                    "name": self.reference,
                    "debit": self.value,
                    "credit": 0,
                    "product_id": self.product_id.id,
                    "quantity": quantity,
                    "product_uom_id": self.product_id.uom_id.id,
                },
            ]

        if self._is_storno_return():
            # transformare în storno (roșu): nota „neagră" de retur (Dr A / Cr B)
            # devine tranzacția originală cu sume negative (Dr B -V / Cr A -V);
            # mecanic: suma trece pe partea opusă, negată, iar cantitatea semnată
            # se inversează odată cu partea
            for vals in vals_list:
                debit = vals.get("debit", 0.0)
                credit = vals.get("credit", 0.0)
                vals["debit"], vals["credit"] = -credit, -debit
                if vals.get("quantity"):
                    vals["quantity"] = -vals["quantity"]
        return vals_list

    def _get_obyc_stock_journal(self):
        """Jurnalul de stoc al ariei de evaluare, pentru produsele cu clasă de
        evaluare OBYC; recordset gol dacă nu se aplică."""
        self.ensure_one()
        journal = self.env["account.journal"]
        if self.product_id.valuation_class_id:
            valuation_area = self._get_valuation_area(raise_if_not_found=False)
            if valuation_area and valuation_area.stock_journal_id:
                journal = valuation_area.stock_journal_id
        return journal

    def _create_account_move(self):
        """Grupează mișcările pe jurnalul ariei de evaluare: mișcările OBYC dintr-o
        arie cu jurnal propriu primesc nota pe acel jurnal; restul merg pe
        comportamentul standard (jurnalul de stoc al companiei)."""
        result = self.env["account.move"]
        default_moves = self.browse()
        by_journal = {}
        for move in self:
            journal = move._get_obyc_stock_journal()
            if journal:
                by_journal.setdefault(journal, self.browse())
                by_journal[journal] |= move
            else:
                default_moves |= move
        if default_moves:
            result |= super(StockMove, default_moves)._create_account_move()
        for journal, moves in by_journal.items():
            result |= moves._create_account_move_with_journal(journal)
        return result

    def _create_account_move_with_journal(self, journal):
        """Replica fluxului core `_create_account_move`, cu jurnalul forțat
        (core-ul folosește necondiționat jurnalul de stoc al companiei)."""
        aml_vals_list = []
        move_to_link = set()
        for move in self:
            if move._should_create_account_move():
                aml_vals_list += move._get_account_move_line_vals()
                move_to_link.add(move.id)
        if not aml_vals_list:
            return self.env["account.move"]

        move_refs = list(set(self.mapped("reference")))
        joined_refs = ", ".join(move_refs)
        if len(joined_refs) > 43:
            joined_refs = joined_refs[:40] + "..."

        account_move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "ref": joined_refs,
                    "partner_id": self._get_partner_id_for_valuation_lines(),
                    "journal_id": journal.id,
                    "line_ids": [Command.create(aml_vals) for aml_vals in aml_vals_list],
                    "date": self.env.context.get("force_period_date") or fields.Date.context_today(self),
                }
            )
        )
        self.env["stock.move"].browse(move_to_link).account_move_id = account_move.id
        account_move._post()
        return account_move
