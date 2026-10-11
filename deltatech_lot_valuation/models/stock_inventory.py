# ©  2008-2026 Deltatech
#              Dan Stoica <danila(@)terrabit(.)ro
# See README.rst file on addons root folder for license details

from odoo import api, models


def _lot_inventory_price(lot):
    """Prețul unitar al lotului pentru inventar; fals dacă lotul nu are preț propriu."""
    if not lot._has_valuation_data():
        return False
    if lot.product_id.tracking == "serial":
        return lot.inventory_value if lot.product_qty else 0.0
    return lot.unit_price


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    def _get_inventory_lines_values(self):
        lines = super()._get_inventory_lines_values()
        for line in lines:
            if line.get("prod_lot_id"):
                price = _lot_inventory_price(self.env["stock.lot"].browse(line["prod_lot_id"]))
                if price is not False:
                    line["standard_price"] = price
        return lines


class StockInventoryLine(models.Model):
    _inherit = "stock.inventory.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines.filtered("prod_lot_id"):
            price = _lot_inventory_price(line.prod_lot_id)
            if price is not False:
                line.standard_price = price
        return lines
