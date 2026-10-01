# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_valuation_area = fields.Boolean(string="Use Valuation Area")
    valuation_area_id = fields.Many2one("valuation.area", string="Valuation Area")
    valuation_keep_move_value = fields.Boolean(
        string="Keep move value on retroactive recompute",
        default=True,
        help="If checked, the value of stock moves already validated stays the one computed at "
        "validation time (the Odoo 19 behaviour, consistent with the posted journal entries). "
        "If unchecked, the standard Odoo 20 recompute rewrites the value of the later outgoing "
        "moves, while the journal entries already posted are NOT corrected, so the stock value "
        "and the accounting can diverge.",
    )
