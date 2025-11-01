# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestValuationArea(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        # Reuse accounting common to have journals/partners/products ready
        super().setUpClass()

        # Ensure no default valuation area on company to begin with
        cls.env.company.valuation_area_id = False

        # Create one valuation area to use in tests
        cls.valuation_area = cls.env["valuation.area"].create(
            {
                "name": "Main Warehouse",
                "code": "MW",
                "company_id": cls.env.company.id,
            }
        )

    def test_display_name_format(self):
        # display_name should be in format: [CODE] Name
        self.assertEqual(self.valuation_area.display_name, "[MW] Main Warehouse")

    def test_invoice_line_requires_valuation_area_when_product(self):
        # With company valuation area unset, creating a stockable product line should
        # trigger the constraint that valuation_area_id is required.
        self.env.company.valuation_area_id = False

        # Ensure the product used is stockable to trigger the constraint
        self.product_a.is_storable = True

        # Prepare a minimal customer invoice using existing fixtures
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product_a.id,  # stockable product
                        "quantity": 1.0,
                        "price_unit": 100.0,
                        # account will be auto-determined from product categories in the common setup
                    }
                )
            ],
        }
        with self.assertRaises(UserError):
            self.env["account.move"].create(invoice_vals)

    def test_invoice_line_gets_company_valuation_area(self):
        # When company has a valuation area defined, invoice line should compute it
        self.env.company.valuation_area_id = self.valuation_area

        # Ensure the product used is stockable
        self.product_a.is_storable = True

        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 2.0,
                            "price_unit": 50.0,
                        }
                    )
                ],
            }
        )

        line = move.invoice_line_ids[:1]
        self.assertEqual(line.valuation_area_id, self.valuation_area)
