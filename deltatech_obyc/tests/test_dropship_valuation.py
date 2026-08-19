# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import Command
from odoo.tests import tagged

from .test_common import TestCommon


@tagged("post_install", "-at_install")
class TestDropshipValuation(TestCommon):
    """Core (`stock_account._set_value`) never assigns `stock.move.value` for a
    pure dropship move (supplier -> customer): the `is_dropship` branch only
    feeds the standard-price recompute, the assignment itself is gated on
    `is_in`. Without the fix in `stock_move._set_value()`, the OBYC journal
    entry generated right after would be posted with debit=0/credit=0."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.account_stock_valuation = cls.env["account.account"].create(
            {"name": "Stock Valuation Cat", "code": "SVC002", "account_type": "asset_current"}
        )
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product.standard_price = 100.0

        cls.env["product.account.determination"].create(
            {
                "transaction_key": "dropship",
                "valuation_class_id": cls.valuation_class.id,
                "valuation_area_id": cls.valuation_area.id,
                "company_id": cls.env.company.id,
                "acc_src_id": cls.account_src.id,
                "acc_dest_id": cls.account_dest.id,
                "acc_valuation_id": cls.account_valuation.id,
            }
        )

        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        # picking_type nu conteaza pentru determinarea transaction_key (bazata
        # doar pe usage-ul locatiilor); reutilizam "out" ca sa avem un tip valid
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

    def _make_dropship(self, qty=5.0):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids._set_quantity_done(qty)
        picking.with_context(demo_mode=True).button_validate()
        return picking.move_ids

    def test_dropship_move_gets_valued(self):
        move = self._make_dropship(qty=5.0)
        self.assertTrue(move.is_dropship)
        self.assertAlmostEqual(
            move.value,
            500.0,
            places=2,
            msg="stock.move.value trebuie completat pentru mișcarea dropship, "
            "nu lăsat la 0 cum îl lasă core stock_account",
        )

    def test_dropship_generates_valued_journal_entry(self):
        move = self._make_dropship(qty=5.0)
        self.assertTrue(move.account_move_id, "Mișcarea dropship trebuie să genereze o notă contabilă")
        self.assertEqual(move.account_move_id.state, "posted")

        lines = move.account_move_id.line_ids
        debit_line = lines.filtered(lambda line: line.debit > 0)
        credit_line = lines.filtered(lambda line: line.credit > 0)
        self.assertTrue(debit_line and credit_line, "Nota generată nu poate avea debit=0/credit=0")
        self.assertAlmostEqual(debit_line.debit, 500.0, places=2)
        self.assertAlmostEqual(credit_line.credit, 500.0, places=2)


@tagged("post_install", "-at_install")
class TestDropshipDoesNotAffectStockValuation(TestCommon):
    """Completarea `stock.move.value` pe mișcarea dropship (fix-ul de mai sus) nu
    trebuie să afecteze valorizarea stocului REAL al aceluiași produs, când acesta
    e ținut și pe stoc (nu doar dropshipped). Dropship-ul nu atinge nicio locație
    internă — cantitatea din gestiune și costul mediu ponderat trebuie să rămână
    neschimbate după o mișcare dropship, indiferent de fix-ul din `_set_value()`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "average",
            }
        )
        cls.product.standard_price = 100.0

        for key in ("stock_receipt", "dropship"):
            cls.env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": cls.env.company.id,
                    "acc_src_id": cls.account_src.id,
                    "acc_dest_id": cls.account_dest.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )

        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

    def _receive(self, qty, product=None):
        product = product or self.product
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids._set_quantity_done(qty)
        picking.button_validate()
        return picking.move_ids

    def _dropship(self, qty, product=None):
        product = product or self.product
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids._set_quantity_done(qty)
        picking.with_context(demo_mode=True).button_validate()
        return picking.move_ids

    def test_dropship_does_not_move_stock_quantity(self):
        """Produsul e ținut și pe stoc (recepție reală); dropship-ul, pe același
        produs, nu trebuie să modifice cantitatea din gestiune — dropship-ul nu
        atinge niciodată o locație internă."""
        self._receive(10.0)
        qty_before = self.product.qty_available
        self._dropship(5.0)
        self.product.invalidate_recordset(["qty_available"])
        self.assertEqual(
            self.product.qty_available,
            qty_before,
            "Dropship-ul nu trebuie să modifice cantitatea reală din gestiune",
        )

    def test_dropship_does_not_change_average_cost(self):
        """Costul mediu ponderat al stocului real trebuie să rămână neschimbat
        după o mișcare dropship pe același produs (produs ținut și pe stoc)."""
        self._receive(10.0)  # 10 buc @ 100 (standard_price) → cost mediu 100
        price_before = self.product.standard_price
        move = self._dropship(5.0)
        self.product.invalidate_recordset(["standard_price"])
        self.assertTrue(move.is_dropship)
        self.assertAlmostEqual(
            self.product.standard_price,
            price_before,
            places=2,
            msg="Dropship-ul nu trebuie să modifice costul mediu ponderat al stocului real",
        )
