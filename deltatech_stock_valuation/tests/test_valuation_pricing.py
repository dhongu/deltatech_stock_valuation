# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestValuationPricing(AccountTestInvoicingCommon):
    """
    Testări pentru funcționalitatea de descărcare de gestiune la prețul din
    `product.valuation` (cost mediu pe arie de evaluare) și pentru constrângerea
    de incompatibilitate cu metoda FIFO.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        # Stock-related accounts and journal needed for accounting valuation data.
        cls.acc_input = cls.env["account.account"].create(
            {"name": "Stock Input", "code": "STKIN1", "account_type": "asset_current"}
        )
        cls.acc_output = cls.env["account.account"].create(
            {"name": "Stock Output", "code": "STKOUT1", "account_type": "asset_current"}
        )
        cls.acc_valuation = cls.env["account.account"].create(
            {
                "name": "Stock Valuation",
                "code": "STKVAL1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        cls.stock_journal = cls.env["account.journal"].create(
            {"name": "Stock Journal", "type": "general", "code": "STJ1"}
        )

        cls.categ_avco = cls.env["product.category"].create(
            {
                "name": "AVCO Valuation Category",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "use_valuation_area_price": True,
                "property_stock_account_input_categ_id": cls.acc_input.id,
                "property_stock_account_output_categ_id": cls.acc_output.id,
                "property_stock_valuation_account_id": cls.acc_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
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

        cls.internal_loc = cls.env["stock.location"].create({"name": "Internal Loc", "usage": "internal"})
        cls.customer_loc = cls.env["stock.location"].create({"name": "Customer Loc", "usage": "customer"})

    def test_fifo_incompatible_with_valuation_area_price(self):
        """
        Constrângerea trebuie să blocheze activarea prețului pe arie de evaluare
        pentru categoriile cu metodă FIFO.
        """
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
        """
        La o ieșire din stoc dintr-o locație internă, prețul unitar trebuie preluat
        din `product.valuation` (nu din standard_price) când categoria are activat
        `use_valuation_area_price`.
        """
        # Înregistrăm o evaluare cu un preț diferit de standard_price.
        valuation = self.env["product.valuation"].get_valuation(
            self.product.id, self.valuation_area.id, self.acc_valuation.id, self.env.company.id
        )
        valuation.write({"quantity": 10.0, "amount": 600.0, "price": 60.0})

        move = self.env["stock.move"].create(
            {
                "name": "Test outgoing",
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 2.0,
                "location_id": self.internal_loc.id,
                "location_dest_id": self.customer_loc.id,
                "company_id": self.env.company.id,
            }
        )

        # In Odoo 18, _get_price_unit returns a price per stock.lot.
        price = move._get_price_unit()
        self.assertEqual(
            price[self.env["stock.lot"]],
            60.0,
            "Outgoing move should be valued at the product.valuation price",
        )

    def test_outgoing_move_without_valuation_falls_back_to_standard(self):
        """
        Dacă nu există evaluare pentru produs, ieșirea trebuie să folosească
        prețul standard (fallback), fără a ridica eroare.
        """
        # Produs fără linie de evaluare.
        product = self.env["product.product"].create(
            {
                "name": "Unvalued Product",
                "is_storable": True,
                "standard_price": 33.0,
                "categ_id": self.categ_avco.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": "Test fallback",
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 1.0,
                "location_id": self.internal_loc.id,
                "location_dest_id": self.customer_loc.id,
                "company_id": self.env.company.id,
            }
        )
        price = move._get_price_unit()
        self.assertEqual(
            price[self.env["stock.lot"]],
            33.0,
            "Should fall back to standard_price when no valuation exists",
        )

    def test_incoming_move_ignores_valuation_price(self):
        """
        Pentru intrări (locație sursă non-internă), prețul nu se preia din evaluare,
        ci se folosește comportamentul standard.
        """
        valuation = self.env["product.valuation"].get_valuation(
            self.product.id, self.valuation_area.id, self.acc_valuation.id, self.env.company.id
        )
        valuation.write({"quantity": 10.0, "amount": 600.0, "price": 60.0})

        supplier_loc = self.env["stock.location"].create({"name": "Supplier Loc", "usage": "supplier"})
        move = self.env["stock.move"].create(
            {
                "name": "Test incoming",
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 2.0,
                "location_id": supplier_loc.id,
                "location_dest_id": self.internal_loc.id,
                "company_id": self.env.company.id,
            }
        )
        price = move._get_price_unit()
        self.assertNotEqual(
            price.get(self.env["stock.lot"]),
            60.0,
            "Incoming moves should not use the valuation price",
        )
