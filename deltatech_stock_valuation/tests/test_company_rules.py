# © 2026 Deltatech
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestValuationCompanyRules(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Valuation company B"})
        product = cls.env["product.product"].create({"name": "Valuation rules product", "type": "consu"})
        cls.rows = {}
        for key, company in (("a", cls.company_a), ("b", cls.company_b)):
            account = cls.env["account.account"].with_company(company).create(
                {"name": f"Stock {key}", "code": f"371{key}9", "account_type": "asset_current"}
            )
            values = {"product_id": product.id, "account_id": account.id, "company_id": company.id}
            cls.rows[key] = (
                cls.env["product.valuation"].create(values),
                cls.env["product.valuation.history"].create(dict(values, month="2026-10")),
            )
        user_values = {"company_id": cls.company_a.id, "company_ids": [Command.set(cls.company_a.ids)]}
        cls.user = new_test_user(cls.env, login="sv_rules_user", groups="base.group_user", **user_values)
        cls.manager = new_test_user(
            cls.env, login="sv_rules_manager", groups="base.group_user,account.group_account_manager", **user_values
        )

    def test_rows_of_other_company_are_hidden(self):
        for model_index, model in enumerate(("product.valuation", "product.valuation.history")):
            for user in (self.user, self.manager):
                found = self.env[model].with_user(user).search([("product_id", "=", self.rows["a"][0].product_id.id)])
                self.assertEqual(found, self.rows["a"][model_index], f"{model} {user.login}")

    def test_manager_cannot_change_other_company_rows(self):
        for record in self.rows["b"]:
            with self.assertRaises(AccessError):
                record.with_user(self.manager).write({"quantity": 99})
        for record in self.rows["a"]:
            record.with_user(self.manager).write({"quantity": 5})
