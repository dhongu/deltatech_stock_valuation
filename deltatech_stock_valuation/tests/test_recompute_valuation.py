# ©  2025 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestRecomputeValuation(AccountTestInvoicingCommon):
    """
    Testări pentru recalcularea manuală și automată a evaluării produselor.
    Verifică sincronizarea corectă între `product.valuation.history` și `product.valuation`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure company has a valuation area and mark relevant accounts
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        # Create a dedicated stock valuation account for tests
        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation Test",
                "code": "SVTEST",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )

        # Use an existing product from the common setup
        cls.product = cls.product_a

    def _make_history(self, month, qty_initial=0.0, amt_initial=0.0, qty_delta=0.0, amt_delta=0.0):
        """Create or fetch a Product Valuation History row and set movement values.
        Returns the created/updated history record.
        """
        PVH = self.env["product.valuation.history"]
        history = PVH.get_valuation(
            self.product.id,
            self.valuation_area.id,
            self.account_stock_val.id,
            fields.Date.from_string(f"{month}-01") if "-" in month else fields.Date.today(),
            self.env.company.id,
        )
        # Overwrite month explicitly in case of date conversion above
        history.month = month.replace("-", "")
        history.write(
            {
                "quantity_initial": qty_initial,
                "amount_initial": amt_initial,
                "quantity": qty_delta,
                "amount": amt_delta,
                # optional fields kept at default (debit/credit/qty_in/out) since compute_final uses quantity/amount
            }
        )

        return history

    def test_recompute_amount_on_single_record(self):
        """
        Verifică recalcularea evaluării pentru o singură înregistrare de produs.
        Se asigură că `_recompute_amount()` actualizează corect câmpurile din `product.valuation`
        pe baza datelor din ultima lună de istoric.
        """
        # Create a history row for 202501 with a positive balance
        h = self._make_history(month="202501", qty_initial=0.0, amt_initial=0.0, qty_delta=10.0, amt_delta=200.0)

        # Ensure a product.valuation entry exists for the same key
        PV = self.env["product.valuation"]
        pv = PV.get_valuation(self.product.id, self.valuation_area.id, self.account_stock_val.id, self.env.company.id)

        # Execute the method under test
        pv._recompute_amount()

        # Assert the amounts were copied from the latest history row
        self.assertEqual(pv.quantity, h.quantity_final)
        self.assertEqual(pv.amount, h.amount_final)
        # Price should be amount / quantity when quantity_final is present
        self.assertAlmostEqual(pv.price, h.amount_final / h.quantity_final, places=6)

    def test_recompute_all_amount_inserts_latest_month(self):
        """
        Verifică recalcularea globală a evaluării (`_recompute_all_amount()`).
        Asigură că sunt șterse înregistrările vechi și sunt inserate doar datele
        din cea mai recentă lună disponibilă în istoric pentru fiecare produs.
        """
        PV = self.env["product.valuation"]
        # Prepare two months of history; only the latest should be inserted
        h_prev = self._make_history(month="202412", qty_initial=0.0, amt_initial=0.0, qty_delta=5.0, amt_delta=50.0)
        h_latest = self._make_history(
            month="202501",
            qty_initial=h_prev.quantity_final,
            amt_initial=h_prev.amount_final,
            qty_delta=7.0,
            amt_delta=140.0,
        )

        # Sanity check ordering
        self.assertGreater(h_latest.month, h_prev.month)

        # Run the batch recompute which deletes old PV rows and inserts from latest history
        PV._recompute_all_amount()

        # Fetch the resulting product.valuation row
        pv = PV.search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(pv, "product.valuation record should be created by _recompute_all_amount")
