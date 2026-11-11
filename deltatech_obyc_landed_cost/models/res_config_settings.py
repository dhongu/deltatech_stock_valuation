# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    landed_cost_method = fields.Selection(related="company_id.landed_cost_method", readonly=False)
    landed_cost_intermediary_account_id = fields.Many2one(
        related="company_id.landed_cost_intermediary_account_id", readonly=False
    )
