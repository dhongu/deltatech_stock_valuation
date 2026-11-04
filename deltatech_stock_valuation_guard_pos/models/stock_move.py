from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _valuation_guard_skip(self):
        """The moves of a POS order are validated when the order reaches the server, after the
        fiscal receipt was printed: refusing them there would leave the order stuck in the register.
        The register stops a product without cost when it is added to the cart instead."""
        return super()._valuation_guard_skip() or bool(self.picking_id.pos_order_id or self.picking_id.pos_session_id)
