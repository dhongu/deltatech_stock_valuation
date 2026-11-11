# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import api, fields, models


class StockReclassificationRule(models.Model):
    _name = "stock.reclassification.rule"
    _description = "Stock Reclassification Rule"
    _order = "company_id, account_src_id, account_dest_id"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    account_src_id = fields.Many2one("account.account", string="Source Account", required=True, check_company=True)
    account_dest_id = fields.Many2one(
        "account.account", string="Destination Account", required=True, check_company=True
    )
    destination_type = fields.Selection(
        selection=[("stock", "Stock account change")],
        string="Destination Type",
        required=True,
        default="stock",
    )
    require_decision = fields.Boolean(
        string="Management Decision Required",
        help="The document cannot be validated without the management decision (the change of "
        "destination of the goods must be supported by a written decision).",
    )
    require_reason = fields.Boolean(string="Reason Required")

    _accounts_differ = models.Constraint(
        "CHECK(account_src_id != account_dest_id)",
        "The source and the destination account must be different.",
    )
    _pair_unique = models.Constraint(
        "UNIQUE(company_id, account_src_id, account_dest_id)",
        "There is already a rule for this pair of accounts.",
    )

    @api.depends("account_src_id.code", "account_dest_id.code")
    def _compute_name(self):
        for rule in self:
            rule.name = f"{rule.account_src_id.code or ''} → {rule.account_dest_id.code or ''}"
