# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    landed_cost_method = fields.Selection(
        [
            ("standard", "Standard (credit class 6 directly)"),
            ("intermediary", "Through intermediary account"),
        ],
        string="Landed Cost Class 6 Method",
        default="standard",
        help="How a landed cost entry that would credit a class 6 (expense) account is generated:\n"
        "- Standard: native Odoo behaviour (stock valuation = class 6);\n"
        "- Through intermediary account: the class 6 credit is routed through a technical "
        "intermediary account, producing a single entry with two balanced pairs (stock valuation = intermediary "
        "and intermediary = class 6) and the same net effect.",
    )
    landed_cost_intermediary_account_id = fields.Many2one(
        "account.account",
        string="Landed Cost Intermediary Account",
        check_company=True,
        help="Technical account used to route the class 6 credit of a landed cost entry. "
        "It nets to zero on every landed cost. Class 609 is never rerouted.",
    )
