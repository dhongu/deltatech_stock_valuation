# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_valuation_report")
class TestValuationCheckReport(AccountTestInvoicingCommon):
    """
    Testări pentru raportul de verificare evaluare vs. balanță:
    soldul contului, totalul liniilor cu produs și diferența (linii fără produs).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.valuation_area_level = "company"
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()

        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation VR",
                "code": "SVVR1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        cls.counterpart_account = cls.company_data["default_account_expense"]
        cls.journal = cls.env["account.journal"].create({"name": "Misc VR", "type": "general", "code": "JVVR"})
        cls.product = cls.product_a
        cls.product.is_storable = True

        cls.report = cls.env.ref("deltatech_valuation_report.valuation_check_report")

    def _post_entry(self, debit, quantity=0.0, with_product=True):
        line = {
            "name": "Stock line",
            "account_id": self.account_stock_val.id,
            "debit": debit,
            "credit": 0.0,
        }
        if with_product:
            line.update(
                {
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "quantity": quantity,
                }
            )
        move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "date": fields.Date.today(),
                "line_ids": [
                    (0, 0, line),
                    (
                        0,
                        0,
                        {
                            "name": "Counterpart",
                            "account_id": self.counterpart_account.id,
                            "debit": 0.0,
                            "credit": debit,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def _get_lines(self):
        today = fields.Date.today()
        options = self.report.get_options(
            {
                "date": {
                    "date_from": fields.Date.to_string(today.replace(day=1)),
                    "date_to": fields.Date.to_string(today),
                    "mode": "range",
                    "filter": "custom",
                },
                "unfold_all": True,
            }
        )
        return self.report._get_lines(options)

    def test_report_balance_vs_valuation(self):
        """Soldul contului = linii cu produs + linii fără produs; diferența trebuie
        să arate exact liniile fără produs."""
        self._post_entry(1000.0, quantity=10.0, with_product=True)
        self._post_entry(70.0, with_product=False)

        lines = self._get_lines()
        account_line = next(
            (
                line
                for line in lines
                if f"account.account~{self.account_stock_val.id}" in line["id"]
                or f"account_id~account.account~{self.account_stock_val.id}" in line["id"]
            ),
            None,
        )
        self.assertTrue(account_line, "raportul trebuie să conțină o linie pentru contul de stoc")

        values = {
            col["expression_label"]: col["no_format"]
            for col in account_line["columns"]
            if col.get("expression_label")
        }
        self.assertEqual(values["balance"], 1070.0)
        self.assertEqual(values["valuation"], 1000.0)
        self.assertEqual(values["difference"], 70.0)

    def test_report_no_difference_when_all_lines_have_product(self):
        """Fără linii fără produs, diferența trebuie să fie zero."""
        self._post_entry(500.0, quantity=5.0, with_product=True)

        lines = self._get_lines()
        account_line = next(
            (line for line in lines if f"account.account~{self.account_stock_val.id}" in line["id"]),
            None,
        )
        self.assertTrue(account_line)
        values = {
            col["expression_label"]: col["no_format"]
            for col in account_line["columns"]
            if col.get("expression_label")
        }
        self.assertEqual(values["balance"], values["valuation"])
        self.assertEqual(values["difference"], 0.0)
