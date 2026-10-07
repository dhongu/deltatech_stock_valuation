# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import api, fields, models


class AccountModifier(models.Model):
    _name = "account.modifier"
    _description = "Account Modifier"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Short code used in account mapping rules")

    @api.depends("code", "name")
    @api.depends_context("formatted_display_name")
    def _compute_display_name(self):
        formatted = self.env.context.get("formatted_display_name")
        for item in self:
            if formatted and item.code:
                item.display_name = f"{item.name}\t--{item.code}--"
            elif formatted:
                item.display_name = item.name
            else:
                item.display_name = f"[{item.code}] {item.name}"
