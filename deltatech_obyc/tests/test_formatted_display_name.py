# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestObycFormattedDisplayName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.valuation_class = cls.env["product.valuation.class"].create({"name": "FDN Class", "code": "FDNC1"})
        cls.modifier = cls.env["account.modifier"].create({"name": "FDN Modifier", "code": "FDNM1"})

    def test_plain_display_name_unchanged(self):
        self.assertEqual(self.valuation_class.display_name, "[FDNC1] FDN Class")
        self.assertEqual(self.modifier.display_name, "[FDNM1] FDN Modifier")

    def test_formatted_display_name(self):
        self.assertEqual(
            self.valuation_class.with_context(formatted_display_name=True).display_name,
            "FDN Class\t--FDNC1--",
        )
        self.assertEqual(
            self.modifier.with_context(formatted_display_name=True).display_name,
            "FDN Modifier\t--FDNM1--",
        )

    def test_name_search_by_code(self):
        result = self.env["product.valuation.class"].name_search("FDNC1")
        self.assertIn(self.valuation_class.id, [rid for rid, _name in result])
        result = self.env["account.modifier"].name_search("FDNM1")
        self.assertIn(self.modifier.id, [rid for rid, _name in result])
