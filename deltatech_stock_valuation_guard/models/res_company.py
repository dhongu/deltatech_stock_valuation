from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    valuation_guard_unique_method = fields.Boolean(
        string="One Cost Method",
        help="Every product category must use the cost method and the valuation of the company.",
    )
    valuation_guard_zero_cost = fields.Boolean(
        string="Block Unvalued Moves",
        help="A stock move of a storable product cannot be validated when it would carry no value: "
        "an incoming move valued at zero, or an outgoing move of a product without cost.",
    )
