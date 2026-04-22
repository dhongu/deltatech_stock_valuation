# ©  2024 Deltatech
# See README.rst file on addons root folder for license details
import json

from odoo.tests import tagged

from .common import StockTestCommon


@tagged("post_install", "-at_install")
class TestStockScenarios(StockTestCommon):
    """Tests for the stock management accounting test framework."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    def _make_scenario(self, json_data, mode="test"):
        return self.env["stock.test.scenario"].create(
            {
                "name": json_data.get("name", "Test"),
                "json_data": json.dumps(json_data),
                "mode": mode,
            }
        )

    def _run_scenario(self, scenario_dict, mode="test"):
        scenario = self._make_scenario(scenario_dict, mode=mode)
        run = self.env["stock.test.run"].create(
            {
                "scenario_id": scenario.id,
                "name": scenario.name,
                "mode": mode,
            }
        )
        run.execute(scenario_dict)
        return run

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def test_create_product_category(self):
        """Step create_product_category creates or finds a category."""
        scenario = {
            "name": "Test create_product_category",
            "lines": [
                {
                    "step": "create_product_category",
                    "name": "Test Categ Stock",
                    "property_cost_method": "average",
                }
            ],
            "expected_account_moves": [],
        }
        run = self._run_scenario(scenario, mode="demo")
        self.assertEqual(run.state, "passed")
        categ = self.env["product.category"].search([("name", "=", "Test Categ Stock")], limit=1)
        self.assertTrue(categ, "Product category should have been created")

    def test_create_partner(self):
        """Step create_partner creates or finds a partner."""
        scenario = {
            "name": "Test create_partner",
            "lines": [
                {
                    "step": "create_partner",
                    "name": "Stock Test Partner",
                    "customer_rank": 1,
                }
            ],
            "expected_account_moves": [],
        }
        run = self._run_scenario(scenario, mode="demo")
        self.assertEqual(run.state, "passed")
        partner = self.env["res.partner"].search([("name", "=", "Stock Test Partner")], limit=1)
        self.assertTrue(partner)

    def test_common_fixtures(self):
        """Verify that common fixtures from StockTestCommon are available."""
        self.assertTrue(self.product_fifo, "product_fifo should be set")
        self.assertTrue(self.product_avg, "product_avg should be set")
        self.assertTrue(self.product_service, "product_service should be set")
        self.assertTrue(self.supplier_1, "supplier_1 should be set")
        self.assertTrue(self.supplier_2, "supplier_2 should be set")
        self.assertTrue(self.customer_1, "customer_1 should be set")
        self.assertTrue(self.customer_2, "customer_2 should be set")
        self.assertTrue(self.location, "location should be set")
        self.assertTrue(self.location_sub_1, "location_sub_1 should be set")
        self.assertTrue(self.location_sub_2, "location_sub_2 should be set")
        self.assertTrue(self.category_fifo, "category_fifo should be set")
        self.assertTrue(self.category_avg, "category_avg should be set")

    def test_create_product(self):
        """Step create_product creates a product with the given code."""
        scenario = {
            "name": "Test create_product",
            "lines": [
                {
                    "step": "create_product",
                    "code": "TST-STOCK-01",
                    "name": "Stock Test Product",
                    "standard_price": 50.0,
                    "list_price": 80.0,
                    "type": "consu",
                }
            ],
            "expected_account_moves": [],
        }
        run = self._run_scenario(scenario, mode="demo")
        self.assertEqual(run.state, "passed")
        product = self.env["product.product"].search([("default_code", "=", "TST-STOCK-01")], limit=1)
        self.assertTrue(product)
        self.assertAlmostEqual(product.list_price, 80.0)

    def test_create_invoice_auto_post(self):
        """create_invoice automatically posts the invoice (no separate post_invoice step needed).
        Uses pre-created customer_1 and product_fifo from StockTestCommon.
        """
        scenario = {
            "name": "Test invoice auto-post flow",
            "lines": [
                {
                    "step": "create_invoice",
                    "key": "invoice",
                    "move_type": "out_invoice",
                    "partner_name": self.customer_1.name,
                    "invoice_lines": [
                        {
                            "product_code": self.product_fifo.default_code or "TST-INV-01",
                            "quantity": 2,
                            "price_unit": 150.0,
                        }
                    ],
                },
            ],
            "expected_account_moves": [],
        }
        run = self._run_scenario(scenario, mode="demo")
        self.assertEqual(run.state, "passed")
        move = self.env["account.move"].search([("state", "=", "posted"), ("move_type", "=", "out_invoice")], limit=1)
        self.assertTrue(move, "Invoice should be posted automatically")

    def test_create_invoice_create_only(self):
        """create_invoice with create_only=true leaves the invoice in draft state."""
        scenario = {
            "name": "Test invoice create_only",
            "lines": [
                {
                    "step": "create_invoice",
                    "key": "invoice",
                    "move_type": "out_invoice",
                    "create_only": True,
                    "partner_name": self.customer_1.name,
                    "invoice_lines": [
                        {
                            "product_code": self.product_fifo.default_code or "TST-INV-01",
                            "quantity": 1,
                            "price_unit": 100.0,
                        }
                    ],
                },
            ],
            "expected_account_moves": [],
        }
        run = self._run_scenario(scenario, mode="demo")
        self.assertEqual(run.state, "passed")
        move = self.env["account.move"].search(
            [("state", "=", "draft"), ("move_type", "=", "out_invoice")], limit=1
        )
        self.assertTrue(move, "Invoice should remain in draft when create_only=True")

    def test_scenario_model_action_execute(self):
        """action_execute on stock.test.scenario runs the scenario and sets state=executed."""
        scenario_dict = {
            "name": "Action Execute Test",
            "lines": [
                {
                    "step": "create_partner",
                    "name": "Action Execute Partner",
                    "customer_rank": 1,
                }
            ],
            "expected_account_moves": [],
        }
        scenario = self._make_scenario(scenario_dict, mode="demo")
        scenario.action_execute()
        self.assertEqual(scenario.state, "executed")

    def test_unknown_step_raises(self):
        """An unknown step name should set state=failed with an error message."""
        scenario_dict = {
            "name": "Unknown step test",
            "lines": [{"step": "nonexistent_step"}],
            "expected_account_moves": [],
        }
        run = self.env["stock.test.run"].create(
            {
                "scenario_id": self._make_scenario(scenario_dict, mode="demo").id,
                "name": "Unknown step test",
                "mode": "demo",
            }
        )
        run.execute(scenario_dict)
        self.assertEqual(run.state, "failed")
        self.assertIn("nonexistent_step", run.error_message or run.log or "")
