# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_create_landed_costs(self):
        """Fill the landed cost created from a vendor bill with the receipts of the purchase
        orders on the bill that are not already covered by a validated landed cost, and take
        the account of each cost line from the matching bill line."""
        res = super().button_create_landed_costs()
        landed_cost = self.env["stock.landed.cost"].browse(res.get("res_id"))
        if not landed_cost:
            return res
        pickings = self.line_ids.purchase_line_id.order_id.picking_ids
        covered = (
            self.env["stock.landed.cost"]
            .search([("state", "=", "done"), ("picking_ids", "in", pickings.ids)])
            .picking_ids
        )
        landed_cost.picking_ids = pickings.filtered(lambda picking: picking not in covered and picking.state == "done")
        # the cost lines mirror the bill lines flagged as landed costs, in the same order:
        # pair them one to one, so two lines of the same product keep their own account
        bill_lines = self.line_ids.filtered("is_landed_costs_line").sorted("id")
        for line, bill_line in zip(landed_cost.cost_lines.sorted("id"), bill_lines, strict=False):
            if line.product_id == bill_line.product_id:
                line.account_id = bill_line.account_id
        return res
