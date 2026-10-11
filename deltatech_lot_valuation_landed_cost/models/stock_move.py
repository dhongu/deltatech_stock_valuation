# © 2026 Terrabit
# See README.rst file on addons root folder for license details

from markupsafe import Markup

from odoo import models
from odoo.tools.float_utils import float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        # Prima valorizare a recepției nu este o modificare de valoare: prețul lotului vine din recepție.
        return super(StockMove, self.with_context(lot_valuation_skip_value_change=True))._action_done(
            cancel_backorder=cancel_backorder
        )

    def _set_value(self, correction_quantity=None):
        """Orice schimbare a valorii unei recepții cu loturi (landed cost, factură furnizor, preț
        din comandă, valoare manuală) se repartizează pe loturile rămase în stoc."""
        if self.env.context.get("lot_valuation_skip_value_change") or correction_quantity:
            return super()._set_value(correction_quantity=correction_quantity)
        tracked = self.filtered(lambda m: m.is_in and m.product_id.tracking != "none" and m.state == "done")
        old_values = {move.id: move.value for move in tracked}
        res = super()._set_value(correction_quantity=correction_quantity)
        for move in tracked:
            delta = move.value - old_values[move.id]
            if not move.company_id.currency_id.is_zero(delta):
                move._propagate_value_change_to_lots(delta)
        return res

    def _get_lot_remaining_qty_by_lot(self):
        """Cantitatea din recepție care se află efectiv în stoc, pe fiecare lot.

        Nucleul stabilește restul din recepție pe produs, după regula FIFO; aici contează lotul
        livrat. Când același lot a intrat pe mai multe recepții, stocul lui se consideră consumat
        întâi din recepțiile mai vechi.
        """
        self.ensure_one()
        result = {}
        for lot in self.move_line_ids.lot_id:
            qty_in_move = sum(
                self.move_line_ids.filtered(lambda ml, lot=lot: ml.lot_id == lot).mapped("quantity_product_uom")
            )
            later_lines = self.env["stock.move.line"].search(
                [
                    ("lot_id", "=", lot.id),
                    ("state", "=", "done"),
                    ("move_id", "!=", self.id),
                    ("move_id.is_in", "=", True),
                    ("move_id.date", ">", self.date),
                ]
            )
            qty_later = sum(later_lines.mapped("quantity_product_uom"))
            result[lot] = max(0.0, min(qty_in_move, lot.product_qty - qty_later))
        return result

    def _get_lot_remaining_qty(self):
        self.ensure_one()
        return sum(self._get_lot_remaining_qty_by_lot().values())

    def _propagate_value_change_to_lots(self, delta):
        """Repartizează `delta` pe loturile mișcării, proporțional cu cantitatea din mișcare care
        se mai află în stoc. Partea deja ieșită din stoc nu mai modifică prețul lotului."""
        self.ensure_one()
        rounding = self.product_id.uom_id.rounding
        valued_qty = self._get_valued_qty()
        if float_is_zero(valued_qty, precision_rounding=rounding):
            return
        currency = self.company_id.currency_id
        for lot, remaining in self._get_lot_remaining_qty_by_lot().items():
            if float_is_zero(remaining, precision_rounding=rounding):
                continue
            value_lot = delta * remaining / valued_qty
            unit_delta = value_lot / lot.product_qty
            old_price = lot.unit_price
            lot.write(
                {
                    "unit_price": old_price + unit_delta,
                    "inventory_value": lot.inventory_value + value_lot,
                }
            )
            # message_post escapează un `str` simplu; fără Markup nota ar afișa tag-urile literal
            lot.message_post(
                body=Markup(
                    "<p>Valoarea recepției {move}: {value:+.2f} {currency} ({delta:+.4f}/buc). "
                    "Preț unitar lot: {old:.4f} → {new:.4f}.</p>"
                ).format(
                    move=self.reference or self.display_name,
                    value=value_lot,
                    currency=currency.symbol,
                    delta=unit_delta,
                    old=old_price,
                    new=lot.unit_price,
                )
            )
