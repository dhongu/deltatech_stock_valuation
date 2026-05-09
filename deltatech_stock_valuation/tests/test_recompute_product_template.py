# ©  2025 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestRecomputeProductTemplate(AccountTestInvoicingCommon):
    """
    Testări pentru recalcularea valorii stocului la nivel de șablon de produs (product.template).
    Verifică dacă metoda `recompute_valuation_amount` propagă corect datele din istoricul
    valorii stocului către înregistrările curente de evaluare.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure the company is configured with a valuation area and mark relevant accounts when needed
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        # Dedicated Stock Valuation account for category; start with the flag False to test auto-flagging
        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation (PT)",
                "code": "SVPT01",
                "account_type": "asset_current",
                "is_for_stock_valuation": False,
            }
        )

        # Category that provides the stock valuation account used by the product template
        cls.categ_with_account = cls.env["product.category"].create(
            {
                "name": "Cat With Valuation Account",
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": cls.account_stock_val.id,
            }
        )

        # Category without valuation account for the negative test
        cls.categ_without_account = cls.env["product.category"].create(
            {
                "name": "Cat Without Account",
                "property_valuation": "manual_periodic",
                "property_cost_method": "standard",
            }
        )

        # Ensure we work with stockable products
        cls.product_a.is_storable = True
        cls.product_b.is_storable = True

    def _make_history(self, product, account, month, qty_initial=0.0, amt_initial=0.0, qty_delta=0.0, amt_delta=0.0):
        """Create a product.valuation.history row for a given product and month, and set values."""
        PVH = self.env["product.valuation.history"]
        # month is expected as 'YYYYMM' or 'YYYY-MM'; build a proper date string 'YYYY-MM-01'
        if "-" in month:
            month_digits = month.replace("-", "")
        else:
            month_digits = month
        date_str = f"{month_digits[:4]}-{month_digits[4:6]}-01"
        date_obj = fields.Date.from_string(date_str)
        hist = PVH.get_valuation(
            product.id,
            self.valuation_area.id,
            account.id,
            date_obj,
            self.env.company.id,
        )
        # Normalize month format to YYYYMM
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

    def test_recompute_valuation_amount_single_variant(self):
        """
        Verifică recalcularea evaluării pentru un produs cu o singură variantă.
        Asigură că datele (cantitate, sumă, preț) sunt preluate corect din ultima lună
        de istoric disponibilă.
        """
        # Assign category with valuation account to product_a's template
        tmpl = self.product_a.product_tmpl_id
        tmpl.categ_id = self.categ_with_account

        # Create history for latest month
        h = self._make_history(self.product_a, self.account_stock_val, month="202501", qty_delta=8.0, amt_delta=160.0)

        # Call the method under test
        tmpl.recompute_valuation_amount()

        PV = self.env["product.valuation"]
        pv = PV.search(
            [
                ("product_id", "=", self.product_a.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(pv, "product.valuation should be created/retrieved by recompute_valuation_amount")
        self.assertEqual(pv.quantity, h.quantity_final)
        self.assertEqual(pv.amount, h.amount_final)
        self.assertAlmostEqual(pv.price, h.amount_final / h.quantity_final, places=6)

        # The method should ensure the account is flagged for stock valuation
        self.assertTrue(self.account_stock_val.is_for_stock_valuation)

    def test_recompute_valuation_amount_skips_templates_without_account(self):
        """
        Verifică faptul că recalcularea este ignorată pentru șabloanele de produs
        care nu au un cont de evaluare a stocului definit în categorie.
        Asigură că nu se creează înregistrări de evaluare eronate.
        """
        # Create an isolated product template without a stock valuation account on its category
        tmpl = self.env["product.template"].create(
            {"name": "No Acc Tmpl", "is_storable": True, "categ_id": self.categ_without_account.id}
        )
        product = tmpl.product_variant_id

        # Safety: ensure no lingering valuation exists for this product
        PV = self.env["product.valuation"]
        PV.search([("product_id", "=", product.id)]).unlink()

        # Calling recompute should not crash and should not create a valuation record for this product
        tmpl.recompute_valuation_amount()
        pv = PV.search(
            [
                ("product_id", "=", product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertFalse(
            pv,
            "No product.valuation for the stock valuation account should be created when category lacks valuation account",
        )
