# © 2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import models

# câmpurile care declanșează în core (20.0) revalorizarea mișcării efectuate
_VALUATION_FIELDS = ("quantity", "location_id", "location_dest_id", "owner_id", "quant_id", "lot_id")


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def write(self, vals):
        """Reține cantitatea valorizată a ieșirilor la prețul ariei înainte de editare.

        În 20 editarea unei mișcări efectuate reia valorizarea
        (`stock.move._set_value(recompute_date=...)`); cu cantitatea veche, ieșirea se
        corectează proporțional, la prețul unitar cu care a fost descărcată (ca
        `_set_value(correction_quantity=...)` din 19)."""
        if any(field in vals for field in _VALUATION_FIELDS):
            moves = self.move_id.filtered(lambda m: m.is_out and m._dsv_uses_valuation_area_price())
            if moves:
                previous_qty = {move.id: move._get_valued_qty() for move in moves}
                self = self.with_context(dsv_previous_valued_qty=previous_qty)  # noqa: PLW0642
        return super().write(vals)
