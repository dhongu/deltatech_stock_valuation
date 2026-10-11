# © 2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _update_stock_move_value(self, old_qty_by_ml=None):
        # Schimbarea cantității unei recepții modifică valoarea mișcării, dar nu costul unitar:
        # prețul loturilor rămâne neschimbat.
        return super(StockMoveLine, self.with_context(lot_valuation_skip_value_change=True))._update_stock_move_value(
            old_qty_by_ml=old_qty_by_ml
        )
