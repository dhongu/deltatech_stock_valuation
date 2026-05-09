# © 2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    use_valuation_area_price = fields.Boolean(
        string="Use Valuation Area Price",
        default=False,
        help="If enabled, stock outgoing moves use the price computed "
        "from product.valuation instead of standard_price.",
    )

    @api.constrains("use_valuation_area_price", "property_cost_method")
    def _check_valuation_area_price_vs_costing_method(self):
        for categ in self:
            if categ.use_valuation_area_price and categ.property_cost_method == "fifo":
                raise ValidationError(
                    _(
                        "Category '%s': Use Valuation Area Price is not compatible "
                        "with FIFO costing method. Please use AVCO.",
                        categ.name,
                    )
                )
