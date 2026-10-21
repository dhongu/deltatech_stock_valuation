from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    valuation_guard_unique_method = fields.Boolean(related="company_id.valuation_guard_unique_method", readonly=False)
    valuation_guard_zero_cost = fields.Boolean(related="company_id.valuation_guard_zero_cost", readonly=False)
    valuation_guard_cost_method = fields.Selection(related="company_id.cost_method", readonly=False)
    valuation_guard_inventory_valuation = fields.Selection(related="company_id.inventory_valuation", readonly=False)

    def action_valuation_guard_align(self):
        self.ensure_one()
        return self.env["product.category"].action_valuation_guard_align()
