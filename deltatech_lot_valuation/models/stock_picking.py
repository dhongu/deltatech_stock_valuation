# ©  2008-2026 Deltatech
#              Dan Stoica <danila(@)terrabit(.)ro
# See README.rst file on addons root folder for license details

from odoo import models
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        # prețurile loturilor se actualizează la recepția de la furnizor
        for picking in self.filtered(lambda p: p.state == "done"):
            picking._update_lot_prices_from_receipt()
        return res

    def _update_lot_prices_from_receipt(self):
        self.ensure_one()
        lines = self.move_line_ids.filtered(
            lambda ml: ml.lot_id and ml.location_id.usage == "supplier" and ml.location_dest_id.usage == "internal"
        )
        for lot, lot_lines in lines.grouped("lot_id").items():
            received_qty = sum(lot_lines.mapped("quantity_product_uom"))
            unit_price = lot_lines[0].move_id._get_price_unit()
            existing_qty = lot.product_qty - received_qty
            if lot._has_valuation_data() and not float_is_zero(
                existing_qty, precision_rounding=lot.product_id.uom_id.rounding
            ):
                lot._check_receipt_price_matches(unit_price, existing_qty)
                # același preț: costul unitar rămâne, crește doar valoarea recepțiilor
                lot.inventory_value += unit_price * received_qty
                continue
            lot.write(
                {
                    "inventory_value": unit_price * received_qty,
                    "input_price": unit_price,
                    "unit_price": unit_price,
                    "input_date": self.scheduled_date,
                }
            )
