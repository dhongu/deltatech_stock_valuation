# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestValuationPricing(AccountTestInvoicingCommon):
    """
    Testări pentru descărcarea de gestiune la prețul din `product.valuation`
    (cost mediu pe arie de evaluare) — în Odoo 19 prin post-procesarea `_set_value` —
    și pentru constrângerea de incompatibilitate cu metoda FIFO.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        cls.acc_valuation = cls.env["account.account"].create(
            {
                "name": "Stock Valuation VP",
                "code": "STKVP1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )

        cls.categ_avco = cls.env["product.category"].create(
            {
                "name": "AVCO Valuation Category",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "use_valuation_area_price": True,
                "property_stock_valuation_account_id": cls.acc_valuation.id,
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Priced Product",
                "is_storable": True,
                "standard_price": 99.0,
                "categ_id": cls.categ_avco.id,
            }
        )

        cls.internal_loc = cls.env["stock.location"].create({"name": "Internal Loc VP", "usage": "internal"})
        cls.customer_loc = cls.env["stock.location"].create({"name": "Customer Loc VP", "usage": "customer"})

    def _make_move(self, product, source, dest, qty):
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": qty,
                "location_id": source.id,
                "location_dest_id": dest.id,
                "company_id": self.env.company.id,
            }
        )
        move._action_confirm()
        move.quantity = qty
        move.picked = True
        return move

    def _set_valuation_price(self, product, price, qty=10.0):
        valuation = self.env["product.valuation"].get_valuation(
            product.id, self.valuation_area.id, self.acc_valuation.id, self.env.company.id
        )
        valuation.write({"quantity": qty, "amount": qty * price, "price": price})
        return valuation

    def test_fifo_incompatible_with_valuation_area_price(self):
        """Constrângerea trebuie să blocheze prețul pe arie pentru categoriile FIFO."""
        with self.assertRaises(ValidationError):
            self.env["product.category"].create(
                {
                    "name": "FIFO Category",
                    "property_valuation": "real_time",
                    "property_cost_method": "fifo",
                    "use_valuation_area_price": True,
                }
            )

    def test_avco_compatible_with_valuation_area_price(self):
        """Pentru AVCO, activarea prețului pe arie de evaluare nu trebuie să ridice eroare."""
        categ = self.env["product.category"].create(
            {
                "name": "AVCO OK",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "use_valuation_area_price": True,
            }
        )
        self.assertTrue(categ.use_valuation_area_price)

    def test_outgoing_move_uses_valuation_price(self):
        """O ieșire dintr-o locație internă trebuie valorizată la prețul din
        product.valuation (nu la standard_price) când categoria are
        use_valuation_area_price."""
        self._set_valuation_price(self.product, 60.0)

        move = self._make_move(self.product, self.internal_loc, self.customer_loc, 2.0)
        move._set_value()

        self.assertEqual(move.value, 120.0, "Outgoing move should be valued at the product.valuation price")

    def test_outgoing_move_without_valuation_falls_back_to_standard(self):
        """Fără evaluare pentru produs, ieșirea folosește prețul standard (fallback)."""
        product = self.env["product.product"].create(
            {
                "name": "Unvalued Product",
                "is_storable": True,
                "standard_price": 33.0,
                "categ_id": self.categ_avco.id,
            }
        )
        move = self._make_move(product, self.internal_loc, self.customer_loc, 1.0)
        move._set_value()

        self.assertEqual(move.value, 33.0, "Should fall back to standard_price when no valuation exists")

    def test_incoming_move_ignores_valuation_price(self):
        """Intrările (locație sursă non-internă) nu preiau prețul din evaluare."""
        self._set_valuation_price(self.product, 60.0)
        supplier_loc = self.env["stock.location"].create({"name": "Supplier Loc VP", "usage": "supplier"})

        move = self._make_move(self.product, supplier_loc, self.internal_loc, 2.0)
        move._set_value()

        self.assertNotEqual(move.value, 120.0, "Incoming moves should not use the valuation price")
