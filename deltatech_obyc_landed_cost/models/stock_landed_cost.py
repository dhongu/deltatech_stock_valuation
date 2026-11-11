# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class StockValuationAdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    def _create_account_move_line(self, credit_account_id, debit_account_id, remaining_qty):
        lines = super()._create_account_move_line(credit_account_id, debit_account_id, remaining_qty)
        return self._route_class6_through_intermediary(lines)

    def _route_class6_through_intermediary(self, lines):
        """Split every class 6 credit (except 609) of the landed cost entry in two balanced
        pairs: stock valuation / intermediary and intermediary / class 6. Active only when the
        company method is 'intermediary' and the intermediary account is set."""
        company = self.cost_id.company_id
        intermediary = company.landed_cost_intermediary_account_id
        if company.landed_cost_method != "intermediary" or not intermediary:
            return lines

        new_lines = []
        for command in lines:
            vals = command[2]
            account = self.env["account.account"].browse(vals.get("account_id"))
            credit = vals.get("credit") or 0.0
            is_class_6 = account.code and account.code.startswith("6") and not account.code.startswith("609")
            if is_class_6 and credit:
                new_lines.append([0, 0, dict(vals, account_id=intermediary.id)])
                new_lines.append([0, 0, dict(vals, account_id=intermediary.id, credit=0.0, debit=credit)])
                new_lines.append([0, 0, dict(vals, account_id=account.id)])
            else:
                new_lines.append(command)
        return new_lines
