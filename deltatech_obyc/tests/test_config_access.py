# © 2026 Deltatech
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestConfigAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "OBYC other company"})
        cls.user = new_test_user(
            cls.env,
            login="obyc_internal",
            groups="base.group_user,stock.group_stock_user",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.manager = new_test_user(
            cls.env,
            login="obyc_manager",
            groups="base.group_user,account.group_account_manager",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.valuation_class = cls.env["product.valuation.class"].create({"name": "OBYC ACL", "code": "OACL"})
        cls.modifier = cls.env["account.modifier"].create({"name": "OBYC ACL", "code": "OACL"})
        cls.rule = cls._rule(cls.company)
        cls.other_rule = cls._rule(cls.other_company)

    @classmethod
    def _rule(cls, company):
        return cls.env["product.account.determination"].create(
            {"transaction_key": "stock_valuation", "valuation_class_id": cls.valuation_class.id, "company_id": company.id}
        )

    def test_internal_user_cannot_change_configuration(self):
        Rule = self.env["product.account.determination"].with_user(self.user)
        for record in (self.rule, self.other_rule):
            with self.assertRaises(AccessError):
                record.with_user(self.user).write({"transaction_key": "price_difference"})
            with self.assertRaises(AccessError):
                record.with_user(self.user).unlink()
        with self.assertRaises(AccessError):
            Rule.create({"transaction_key": "stock_valuation", "company_id": self.company.id})
        for record in (self.valuation_class, self.modifier):
            with self.assertRaises(AccessError):
                record.with_user(self.user).write({"name": "tampered"})

    def test_internal_user_reads_only_own_company_rules(self):
        Rule = self.env["product.account.determination"].with_user(self.user)
        found = Rule.search([("valuation_class_id", "=", self.valuation_class.id)])
        self.assertEqual(found, self.rule)

    def test_account_manager_configures(self):
        self.rule.with_user(self.manager).write({"transaction_key": "price_difference"})
        new = self.env["product.account.determination"].with_user(self.manager).create(
            {"transaction_key": "stock_valuation", "company_id": self.company.id}
        )
        new.unlink()
        self.modifier.with_user(self.manager).write({"name": "renamed"})
        self.assertEqual(self.rule.transaction_key, "price_difference")
