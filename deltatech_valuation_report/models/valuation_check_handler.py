# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import models
from odoo.tools import SQL


class ValuationCheckReportHandler(models.AbstractModel):
    _name = "valuation.check.report.handler"
    _inherit = "account.report.custom.handler"
    _description = "Stock Valuation vs Balance Check Report Handler"

    def _get_stock_account_ids(self, options):
        """Conturile marcate pentru evaluarea stocului, în companiile selectate."""
        company_ids = [c["id"] for c in options.get("companies", [])] or self.env.company.ids
        accounts = (
            self.env["account.account"]
            .with_context(allowed_company_ids=company_ids)
            .search([("is_for_stock_valuation", "=", True)])
        )
        return accounts.ids

    def _report_custom_engine_valuation_check(
        self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None
    ):
        """
        Motor custom: pentru fiecare cont de stoc compară soldul contabil complet
        cu totalul liniilor purtătoare de produs (= ce agregă evaluarea, prin definiție).
        Diferența = liniile fără produs, care nu pot intra în evaluarea pe produs.
        """
        self.env.flush_all()

        company_ids = [c["id"] for c in options.get("companies", [])] or self.env.company.ids
        account_ids = self._get_stock_account_ids(options)
        date_to = options["date"]["date_to"]

        empty = {"balance": 0.0, "valuation": 0.0, "difference": 0.0, "has_sublines": False}
        if not account_ids:
            return [] if current_groupby else dict(empty)

        sql = SQL(
            """
            SELECT l.account_id AS grouping_key,
                   SUM(l.debit - l.credit) AS balance,
                   SUM(CASE WHEN l.product_id IS NOT NULL THEN l.debit - l.credit ELSE 0 END) AS valuation,
                   SUM(CASE WHEN l.product_id IS NULL THEN l.debit - l.credit ELSE 0 END) AS difference
            FROM account_move_line l
                JOIN account_move m ON m.id = l.move_id
            WHERE m.state = 'posted'
              AND l.account_id IN %(account_ids)s
              AND l.company_id IN %(company_ids)s
              AND l.date <= %(date_to)s
            GROUP BY l.account_id
            ORDER BY l.account_id
            """,
            account_ids=tuple(account_ids),
            company_ids=tuple(company_ids),
            date_to=date_to,
        )
        self.env.cr.execute(sql)
        rows = self.env.cr.dictfetchall()

        if current_groupby == "account_id":
            return [
                (
                    row["grouping_key"],
                    {
                        "balance": row["balance"],
                        "valuation": row["valuation"],
                        "difference": row["difference"],
                        "has_sublines": False,
                    },
                )
                for row in rows
            ]

        # linia totalizatoare
        return {
            "balance": sum(row["balance"] for row in rows),
            "valuation": sum(row["valuation"] for row in rows),
            "difference": sum(row["difference"] for row in rows),
            "has_sublines": False,
        }

    def _caret_options_initializer(self):
        res = super()._caret_options_initializer()
        res["valuation_check_aml"] = [
            {"name": self.env._("Lines without product"), "action": "open_lines_without_product"},
        ]
        return res

    def _custom_groupby_line_completer(self, report, options, line_dict, current_groupby):
        super()._custom_groupby_line_completer(report, options, line_dict, current_groupby)
        if current_groupby == "account_id":
            line_dict["caret_options"] = "valuation_check_aml"

    def open_lines_without_product(self, options, params):
        """Deschide liniile contabile fără produs de pe contul liniei selectate —
        explicația concretă a diferenței dintre evaluare și balanță."""
        report = self.env["account.report"].browse(options["report_id"])
        account_id = None
        for markup, model, value in report._parse_line_id(params["line_id"]):
            if model == "account.account":
                account_id = int(value)
        domain = [
            ("account_id", "=", account_id),
            ("product_id", "=", False),
            ("parent_state", "=", "posted"),
            ("date", "<=", options["date"]["date_to"]),
        ]
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Lines without product"),
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": domain,
            "context": {"create": False},
        }
