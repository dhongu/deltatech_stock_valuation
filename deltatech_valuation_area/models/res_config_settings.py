# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_valuation_area = fields.Boolean(
        related="company_id.use_valuation_area", string="Use Valuation Area", readonly=False
    )
    valuation_area_id = fields.Many2one(
        "valuation.area", related="company_id.valuation_area_id", string="Valuation Area", readonly=False
    )
