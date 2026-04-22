# ©  2024 Deltatech
# See README.rst file on addons root folder for license details

import logging

from odoo.tests import tagged
from odoo.tools import float_compare

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class AccountScenarioCommon(AccountTestInvoicingCommon):
    """Base class for stock management accounting tests.

    Provides pre-created common fixtures:
      - product categories (FIFO and Average cost)
      - storable products (fifo, average) and a service product
      - supplier and customer partners
      - stock locations (main, sub-locations, second warehouse)
      - account references (income, expense, valuation)

    Subclasses only need to call super().setUpClass() and can immediately
    use cls.product_fifo, cls.supplier_1, cls.location, etc.
    """

    log_checks = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ------------------------------------------------------------------ #
        # Stock journal
        # ------------------------------------------------------------------ #
        cls.stock_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )
        if not cls.stock_journal:
            cls.stock_journal = cls.env["account.journal"].create(
                {
                    "name": "Stock Journal",
                    "code": "STJ",
                    "type": "general",
                    "company_id": cls.env.company.id,
                }
            )

        # ------------------------------------------------------------------ #
        # Product categories
        # ------------------------------------------------------------------ #
        stock_val_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "asset_current"),
                ("company_ids", "in", cls.env.company.id),
            ],
            limit=1,
        )

        cls.category_fifo = cls.env["product.category"].create(
            {
                "name": "Test Category FIFO",
                "property_valuation": "real_time",
                "property_cost_method": "fifo",
                "property_stock_valuation_account_id": stock_val_account.id,
            }
        )
        cls.category_avg = cls.env["product.category"].create(
            {
                "name": "Test Category Average",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": stock_val_account.id,
            }
        )

        # ------------------------------------------------------------------ #
        # Products
        # ------------------------------------------------------------------ #
        cls.product_fifo = cls.env["product.product"].create(
            {
                "name": "Product FIFO",
                "default_code": "PROD-FIFO-001",
                "is_storable": True,
                "categ_id": cls.category_fifo.id,
                "invoice_policy": "delivery",
                "purchase_method": "receive",
                "standard_price": 100.0,
                "list_price": 150.0,
            }
        )
        cls.product_avg = cls.env["product.product"].create(
            {
                "name": "Product Average",
                "default_code": "PROD-AVG-001",
                "is_storable": True,
                "categ_id": cls.category_avg.id,
                "invoice_policy": "delivery",
                "purchase_method": "receive",
                "standard_price": 80.0,
                "list_price": 120.0,
            }
        )
        cls.product_service = cls.env["product.product"].create(
            {
                "name": "Service Product",
                "type": "service",
                "invoice_policy": "order",
                "purchase_method": "purchase",
                "standard_price": 50.0,
                "list_price": 75.0,
            }
        )

        # ------------------------------------------------------------------ #
        # Partners
        # ------------------------------------------------------------------ #
        cls.supplier_1 = cls.env["res.partner"].create(
            {
                "name": "Test Supplier 1",
                "supplier_rank": 1,
                "company_type": "company",
            }
        )
        cls.supplier_2 = cls.env["res.partner"].create(
            {
                "name": "Test Supplier 2",
                "supplier_rank": 1,
                "company_type": "company",
            }
        )
        cls.customer_1 = cls.env["res.partner"].create(
            {
                "name": "Test Customer 1",
                "customer_rank": 1,
                "company_type": "company",
            }
        )
        cls.customer_2 = cls.env["res.partner"].create(
            {
                "name": "Test Customer 2",
                "customer_rank": 1,
                "company_type": "company",
            }
        )

        # ------------------------------------------------------------------ #
        # Warehouse & locations
        # ------------------------------------------------------------------ #
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.location = cls.warehouse.lot_stock_id

        cls.location_sub_1 = cls.env["stock.location"].create(
            {
                "name": "Stock Sub Location 1",
                "usage": "internal",
                "location_id": cls.location.id,
            }
        )
        cls.location_sub_2 = cls.env["stock.location"].create(
            {
                "name": "Stock Sub Location 2",
                "usage": "internal",
                "location_id": cls.location.id,
            }
        )

        cls.location_supplier = cls.env["stock.location"].search(
            [("usage", "=", "supplier"), ("company_id", "in", [False, cls.env.company.id])],
            limit=1,
        )
        cls.location_customer = cls.env["stock.location"].search(
            [("usage", "=", "customer"), ("company_id", "in", [False, cls.env.company.id])],
            limit=1,
        )

        # ------------------------------------------------------------------ #
        # Account references
        # ------------------------------------------------------------------ #
        cls.account_income = cls.env.company.income_account_id
        cls.account_expense = cls.env.company.expense_account_id

    # ---------------------------------------------------------------------- #
    # Check helpers (same API as l10n_ro_stock_account/tests/common.py)
    # ---------------------------------------------------------------------- #

    def check_accounting_entries(self, checks):
        """Verify cumulative balance per account code.

        ``checks`` is a dict: {account_code: expected_balance}
        """
        if self.log_checks:
            acc_moves = self.env["account.move"].search(
                [("company_id", "=", self.env.company.id), ("state", "=", "posted")],
                order="id",
            )
            for move in acc_moves:
                _logger.info("-" * 80)
                _logger.info("%-20s | %-10s | %-10s | %-10s | %s", "Document", "Account", "Debit", "Credit", "Balance")
                _logger.info("-" * 80)
                for line in move.line_ids:
                    _logger.info(
                        "%-20s | %-10s | %10.2f | %10.2f | %10.2f",
                        line.move_id.name,
                        line.account_id.code,
                        line.debit,
                        line.credit,
                        line.balance,
                    )

        for account_code, expected_balance in checks.items():
            account = self.env["account.account"].search(
                [
                    ("code", "=", account_code),
                    ("company_ids", "in", self.env.company.id),
                ],
                limit=1,
            )
            if not account:
                raise AssertionError(f"Account with code {account_code} not found")

            lines = self.env["account.move.line"].search(
                [
                    ("account_id", "=", account.id),
                    ("company_id", "=", self.env.company.id),
                    ("parent_state", "=", "posted"),
                ]
            )
            if not lines and float(expected_balance) != 0.0:
                raise AssertionError(f"No posted entries found for account {account_code}")

            balance = sum(lines.mapped("balance"))
            self.assertEqual(
                float_compare(balance, float(expected_balance), precision_rounding=0.01),
                0,
                f"Account {account_code} balance expected {expected_balance}, got {balance}",
            )

    def check_stock_levels(self, checks):
        """Verify stock quantity and value per product/location.

        ``checks`` is a dict: {product_attr: [{location, qty, value}, ...]}
        where ``product_attr`` is an attribute name on ``self`` (e.g. 'product_fifo').
        """
        for product_ref, check_list in checks.items():
            product = getattr(self, product_ref)
            for vals in check_list:
                if vals.get("location"):
                    location = getattr(self, vals["location"])
                    quant_domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "=", location.id),
                    ]
                else:
                    locations = self.env["stock.location"].search(
                        [
                            ("usage", "in", ("internal", "transit")),
                            ("company_id", "=", self.env.company.id),
                        ]
                    )
                    quant_domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "in", locations.ids),
                    ]

                quants = self.env["stock.quant"].search(quant_domain)
                total_qty = sum(quants.mapped("quantity"))
                total_value = sum(quants.mapped("value"))

                if self.log_checks:
                    _logger.info("Stock quants for %s:", product.name)
                    for q in quants:
                        _logger.info(
                            "  %s | qty=%.2f | value=%.2f",
                            q.location_id.display_name,
                            q.quantity,
                            q.value,
                        )

                if "qty" in vals:
                    self.assertEqual(
                        float_compare(total_qty, float(vals["qty"]), precision_rounding=0.01),
                        0,
                        f"Stock qty for {product.name} expected {vals['qty']}, got {total_qty}",
                    )
                if "value" in vals:
                    self.assertEqual(
                        float_compare(total_value, float(vals["value"]), precision_rounding=0.01),
                        0,
                        f"Stock value for {product.name} expected {vals['value']}, got {total_value}",
                    )

    def run_checks(self, checks):
        """Dispatch accounting and stock checks."""
        if "account" in checks:
            self.check_accounting_entries(checks["account"])
        if "stock" in checks:
            self.check_stock_levels(checks["stock"])
