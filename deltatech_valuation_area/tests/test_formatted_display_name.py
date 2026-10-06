# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestValuationAreaFormattedDisplayName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.area = cls.env["valuation.area"].create({"name": "FDN Area", "code": "FDNA1"})

    def test_plain_display_name_unchanged(self):
        self.assertEqual(self.area.display_name, "[FDNA1] FDN Area")

    def test_formatted_display_name(self):
        area = self.area.with_context(formatted_display_name=True)
        self.assertEqual(area.display_name, "FDN Area\t--FDNA1--")

    def test_name_search_by_code(self):
        result = self.env["valuation.area"].name_search("FDNA1")
        self.assertIn(self.area.id, [rid for rid, _name in result])
