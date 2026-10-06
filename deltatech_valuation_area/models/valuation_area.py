# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import api, fields, models


class ValuationArea(models.Model):
    _name = "valuation.area"
    _description = "Valuation Area"
    _check_company_auto = True
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Short code shown in front of the area name, as [CODE] Name.")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    stock_journal_id = fields.Many2one(
        "account.journal",
        string="Stock Journal",
        domain=[("type", "=", "general")],
        check_company=True,
    )

    @api.depends("code", "name")
    @api.depends_context("formatted_display_name")
    def _compute_display_name(self):
        """
        Format the display name as [CODE] Name; in the many2one dropdown the code
        is shown in a second, dimmed column.
        """
        formatted = self.env.context.get("formatted_display_name")
        for item in self:
            if formatted and item.code:
                item.display_name = f"{item.name}\t--{item.code}--"
            elif formatted:
                item.display_name = item.name
            else:
                item.display_name = f"[{item.code}] {item.name}"
