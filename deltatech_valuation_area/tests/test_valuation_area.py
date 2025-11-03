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

    def test_stock_move_accounting_sets_valuation_area(self):
        """
        Validate a real-time valued stock move generates accounting entries and
        our stock.move override sets valuation_area_id on the move lines.
        """
        company = self.env.company
        # Ensure valuation area is set so _get_valuation_area() doesn't raise.
        company.valuation_area_id = self.valuation_area

        # Use a stockable product
        self.product_a.is_storable = True

        stock_valuation_account = self.env["account.account"].create(
            {
                "name": "Stock Valuation",
                "code": "SV0001",
                "account_type": "asset_current",
            }
        )
        stock_input_account = self.env["account.account"].create(
            {
                "name": "Stock Interim (In)",
                "code": "SVIN01",
                "account_type": "asset_current",
            }
        )
        stock_output_account = self.env["account.account"].create(
            {
                "name": "Stock Interim (Out)",
                "code": "SVOUT1",
                "account_type": "asset_current",
            }
        )
        cogs_account = self.env["account.account"].create(
            {
                "name": "COGS",
                "code": "COGS01",
                "internal_group": "expense",
                "account_type": "asset_current",
            }
        )

        stock_journal = self.env["account.journal"].create({"name": "Stock Journal", "type": "general", "code": "STK"})

        # Create a product category with real-time valuation and proper accounts
        categ = self.env["product.category"].create(
            {
                "name": "Valued Cat",
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": stock_valuation_account.id,
                "property_stock_account_input_categ_id": stock_input_account.id,
                "property_stock_account_output_categ_id": stock_output_account.id,
                "property_stock_journal": stock_journal.id,
                # Some DBs also use expense account on category for dropship/cogs; harmless here
                "property_account_expense_categ_id": cogs_account.id,
            }
        )
        self.product_a.categ_id = categ
        # Set a standard cost to avoid zero-cost edge cases
        self.product_a.standard_price = 10.0

        # Get warehouse and locations
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        self.assertTrue(warehouse, "No warehouse found for the current company")
        stock_location = warehouse.lot_stock_id
        customer_location = self.env.ref("stock.stock_location_customers")

        # Put some stock on hand via quant adjustment
        self.env["stock.quant"]._update_available_quantity(self.product_a, stock_location, 5.0)

        # Create an outgoing picking to customer
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": stock_location.id,
                "location_dest_id": customer_location.id,
                "move_ids_without_package": [
                    Command.create(
                        {
                            "name": self.product_a.display_name,
                            "product_id": self.product_a.id,
                            "product_uom_qty": 2.0,
                            "product_uom": self.product_a.uom_id.id,
                            "location_id": stock_location.id,
                            "location_dest_id": customer_location.id,
                        }
                    )
                ],
            }
        )

        picking.action_confirm()
        picking.move_ids._set_quantity_done(2.0)

        res = picking.button_validate()
        if isinstance(res, dict) and res.get("res_model") == "stock.immediate.transfer":
            wiz = self.env[res["res_model"]].browse(res["res_id"])
            wiz.process()

        # Fetch the accounting moves generated for this picking's stock moves
        account_moves = self.env["account.move"].search([("stock_move_id", "in", picking.move_ids.ids)])
        self.assertTrue(account_moves, "No account moves generated for stock move")

        # All move lines for our product should carry the valuation area
        for ml in account_moves.mapped("line_ids"):
            if ml.product_id == self.product_a:
                self.assertEqual(
                    ml.valuation_area_id,
                    self.valuation_area,
                    "valuation_area_id on account.move.line should be set from stock.move _get_valuation_area",
                )
