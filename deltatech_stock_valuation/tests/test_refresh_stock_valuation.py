# ©  2025 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

import logging

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestRefreshStockValuation(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure company-level valuation is configured and a valuation area exists
        cls.env.company.valuation_area_level = "company"
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        # Dedicated Stock Valuation account used by PVH/PV
        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation (RCS)",
                "code": "SVRCS1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,  # important: picked by recompute_all
            }
        )

        # Use an existing product from common fixtures
        cls.product = cls.product_a
        cls.product.is_storable = True

    def _make_history(self, month, qty_initial=0.0, amt_initial=0.0, qty_delta=0.0, amt_delta=0.0):
        """Create product.valuation.history for (product, valuation_area, account) and set values."""
        PVH = self.env["product.valuation.history"]
        # Support YYYYMM or YYYY-MM
        month_digits = month.replace("-", "")
        date_str = f"{month_digits[:4]}-{month_digits[4:6]}-01"
        date_obj = fields.Date.from_string(date_str)
        hist = PVH.get_valuation(
            self.product.id,
            self.valuation_area.id,
            self.account_stock_val.id,
            date_obj,
            self.env.company.id,
        )
        hist.month = month_digits
        hist.write(
            {
                "quantity_initial": qty_initial,
                "amount_initial": amt_initial,
                "quantity": qty_delta,
                "amount": amt_delta,
            }
        )
        return hist

    def _new_settings(self, with_user=None):
        # Transient model; company is taken from env/company_id field
        Settings = self.env["res.config.settings"]
        s = Settings.create({"company_id": self.env.company.id})
        return s if with_user is None else s.with_user(with_user)

    def test_refresh_stock_valuation_creates_product_valuation(self):
        # Seed real accounting data so product.valuation.history recompute has a period window
        journal = self.env["account.journal"].create({"name": "Misc JV", "type": "general", "code": "JVSV"})
        move = self.env["account.move"].create(
            {
                "journal_id": journal.id,
                "line_ids": [
                    # Debit stock valuation account with product and quantity
                    (
                        0,
                        0,
                        {
                            "name": "Seed SV",
                            "account_id": self.account_stock_val.id,
                            "debit": 140.0,
                            "credit": 0.0,
                            "product_id": self.product.id,
                            "product_uom_id": self.product.uom_id.id,
                            "quantity": 7.0,
                        },
                    ),
                    # Credit counterpart (any account)
                    (
                        0,
                        0,
                        {
                            "name": "Seed SV counterpart",
                            "account_id": self.company_data["default_account_revenue"].id,
                            "debit": 0.0,
                            "credit": 140.0,
                        },
                    ),
                ],
            }
        )
        move.action_post()

        # Update valuation_area_id on move lines if not set
        self.env.cr.execute(
            "UPDATE account_move_line SET valuation_area_id = %s WHERE move_id = %s",
            (self.valuation_area.id, move.id),
        )
        move.line_ids.invalidate_recordset(["valuation_area_id"])

        self.env.cr.execute(
            "SELECT count(*) FROM account_move_line WHERE valuation_area_id = %s", (self.valuation_area.id,)
        )
        _logger.info("Found %s move lines for area %s", self.env.cr.fetchone()[0], self.valuation_area.id)

        PV = self.env["product.valuation"]
        PV.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ]
        ).unlink()

        # Execute refresh; history will be rebuilt from posted move lines
        self._new_settings().refresh_stock_valuation()

        pv = PV.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(pv, "product.valuation record should be created by refresh_stock_valuation")

        # Validate against latest history month actually computed by the refresh
        PVH = self.env["product.valuation.history"]
        h_latest = PVH.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            order="month desc",
            limit=1,
        )
        self.assertTrue(h_latest, "history should be present after refresh")
        self.assertEqual(pv.quantity, h_latest.quantity_final)
        self.assertEqual(pv.amount, h_latest.amount_final)

    def test_refresh_requires_system_user(self):
        # Ensure preconditions so the method does not early-return
        self.env.company.valuation_area_level = "company"
        self._make_history("202501", qty_delta=3.0, amt_delta=30.0)

        # Create a normal internal user without the System group
        user = self.env["res.users"].create(
            {
                "name": "Normal User",
                "login": "normal_user_refresh",
                "email": "normal@example.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        with self.assertRaises(UserError):
            self._new_settings(with_user=user).refresh_stock_valuation()

    def test_refresh_noop_when_not_company_level(self):
        # Switch to warehouse-level so the method returns early
        self.env.company.valuation_area_level = "warehouse"
        # Prepare history
        self._make_history("202501", qty_delta=2.0, amt_delta=20.0)

        PV = self.env["product.valuation"]
        PV.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ]
        ).unlink()

        self._new_settings().refresh_stock_valuation()

        pv = PV.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertFalse(pv, "No product.valuation should be created when valuation_area_level != 'company'")
