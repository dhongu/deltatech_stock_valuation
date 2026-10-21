from datetime import timedelta

from odoo import api, fields, models


class StockValuationGuard(models.AbstractModel):
    _name = "stock.valuation.guard"
    _description = "Stock Valuation Guard - control lists"

    ZERO_MOVE_DAYS = 30

    @api.model
    def _window(self, model, name, domain, view_mode="list,form"):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": view_mode,
            "domain": domain,
            "context": {"create": False},
        }

    @api.model
    def action_misaligned_categories(self):
        categories = self.env["product.category"]._valuation_guard_all_misaligned()
        return self._window(
            "product.category", self.env._("Categories with Another Cost Method"), [("id", "in", categories.ids)]
        )

    @api.model
    def action_products_without_cost(self):
        return self._window(
            "product.product",
            self.env._("Storable Products without Cost"),
            [("is_storable", "=", True), ("standard_price", "<=", 0)],
        )

    @api.model
    def action_zero_valued_stock(self):
        """Incoming moves valued at zero that still have quantity left in the FIFO stack:
        the next deliveries of these products will leave the stock at zero cost."""
        moves = self.env["stock.move"].search(
            [
                ("state", "=", "done"),
                ("is_in", "=", True),
                ("value", "=", 0),
                ("product_id.is_storable", "=", True),
                ("company_id", "=", self.env.company.id),
            ]
        )
        moves = moves.filtered(lambda m: m.remaining_qty > 0)
        return self._window("stock.move", self.env._("Stock Valued at Zero"), [("id", "in", moves.ids)])

    @api.model
    def action_zero_valued_moves(self):
        since = fields.Datetime.now() - timedelta(days=self.ZERO_MOVE_DAYS)
        return self._window(
            "stock.move",
            self.env._("Moves Valued at Zero (last %(days)s days)", days=self.ZERO_MOVE_DAYS),
            [
                ("state", "=", "done"),
                ("date", ">=", since),
                ("value", "=", 0),
                ("product_id.is_storable", "=", True),
                ("company_id", "=", self.env.company.id),
                "|",
                ("is_in", "=", True),
                ("is_out", "=", True),
            ],
        )
