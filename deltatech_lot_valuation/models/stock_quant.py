# ©  2015-2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    price_unit = fields.Monetary(compute="_compute_value", currency_field="currency_id")

    @api.depends("lot_id.unit_price", "lot_id.inventory_value")
    def _compute_value(self):
        res = super()._compute_value()
        for quant in self:
            lot = quant.lot_id
            if (
                lot
                and lot._has_valuation_data()
                and quant.location_id._should_be_valued()
                and not quant._should_exclude_for_valuation()
                and not quant.product_id.uom_id.is_zero(quant.quantity)
            ):
                if quant.product_id.tracking == "serial":
                    quant.value = lot.inventory_value if quant.quantity else 0.0
                else:
                    quant.value = lot.unit_price * quant.quantity
            if quant.quantity:
                quant.price_unit = quant.value / quant.quantity
            else:
                quant.price_unit = quant.product_id.standard_price
        return res
