# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Prețul pe aria de evaluare (deltatech_stock_valuation) pe produsele OBYC: conturile nu vin de pe
# categorie, deci evaluarea se caută pe contul de evaluare din regula OBYC a mișcării.

from odoo.tests import tagged

from .test_obyc_entries import TestObycEntries


@tagged("post_install", "-at_install")
class TestObycAreaPrice(TestObycEntries):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.valuation" not in cls.env:
            return
        cls.account_valuation.is_for_stock_valuation = True
        cls.product_category.use_valuation_area_price = True

    def setUp(self):
        super().setUp()
        if "product.valuation" not in self.env:
            self.skipTest("deltatech_stock_valuation nu este instalat")

    def _valuation(self):
        return self.env["product.valuation"].get_valuation(
            self.product.id, self.valuation_area.id, self.account_valuation.id, self.env.company.id
        )

    def test_delivery_uses_area_price(self):
        self._receipt(10.0)
        self._valuation().write({"price": 60.0})
        delivery = self._delivery(4.0)
        self.assertAlmostEqual(delivery.move_ids.value, 240.0)
        self.assertRecordValues(
            self._lines(delivery),
            [
                {"account_id": self.account_dest.id, "debit": 240.0, "credit": 0.0, "quantity": 4.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 240.0, "quantity": -4.0},
            ],
        )

    def test_delivery_without_area_valuation_uses_standard_price(self):
        self._receipt(10.0)
        self._valuation().write({"price": 0.0})
        delivery = self._delivery(4.0)
        self.assertAlmostEqual(delivery.move_ids.value, 400.0)
