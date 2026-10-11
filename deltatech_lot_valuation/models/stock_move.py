# ©  2015-2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._set_initial_lot_price()
        return moves

    def _set_initial_lot_price(self):
        """Lotul fără niciun preț primește costul unitar al primei intrări în stoc."""
        for move in self.filtered(lambda m: m.is_in and m.product_id.tracking != "none"):
            unit_price = move._get_price_unit()
            if not unit_price:
                continue
            for lot in move.move_line_ids.lot_id:
                if lot._has_valuation_data() or lot.input_price:
                    continue
                qty = sum(
                    move.move_line_ids.filtered(lambda ml, lot=lot: ml.lot_id == lot).mapped("quantity_product_uom")
                )
                lot.write({"unit_price": unit_price, "input_price": unit_price, "inventory_value": unit_price * qty})

    def _set_value(self, correction_quantity=None):
        """Ieșirile produselor cu urmărire se valorizează la prețul propriu al fiecărui lot.

        Nucleul valorizează ieșirea la costul produsului; aici valoarea mișcării devine suma
        `preț lot × cantitate` pe fiecare linie. Liniile fără lot sau cu lot fără preț rămân la
        costul unitar calculat de nucleu.
        """
        res = super()._set_value(correction_quantity=correction_quantity)
        if correction_quantity:
            # super() ajustează proporțional o valoare care era deja la prețul loturilor
            return res
        for move in self:
            if move.product_id.tracking == "none" or move.is_in or move.is_dropship or not move._is_out():
                continue
            move._set_value_from_lot_prices()
        return res

    def _set_value_from_lot_prices(self):
        self.ensure_one()
        lines = self._get_out_move_lines()
        if not any(line.lot_id._has_valuation_data() for line in lines):
            return
        valued_qty = self._get_valued_qty()
        core_unit_cost = self.value / valued_qty if valued_qty else 0.0
        value = 0.0
        for line in lines:
            qty = line.quantity_product_uom
            lot = line.lot_id
            if lot and lot._has_valuation_data():
                value += self._get_lot_line_value(lot, qty)
            else:
                value += core_unit_cost * qty
        self.value = self.company_id.currency_id.round(value)

    def _get_lot_line_value(self, lot, qty):
        if self.product_id.tracking == "serial" and lot.inventory_value:
            return lot.inventory_value
        return lot.unit_price * qty
