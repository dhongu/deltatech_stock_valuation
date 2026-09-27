# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_valuation_area = fields.Boolean(string="Use Valuation Area")
    valuation_area_id = fields.Many2one("valuation.area", string="Valuation Area")
