import json

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestValuationGuard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cost_method": "fifo", "inventory_valuation": "real_time"})
        cls.categ = cls.env["product.category"].create(
            {"name": "Guard FIFO", "property_cost_method": "fifo", "property_valuation": "real_time"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Guard Product", "is_storable": True, "categ_id": cls.categ.id, "standard_price": 0.0}
        )
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.customer = cls.env.ref("stock.stock_location_customers")

    def _move(self, src, dest, qty=5.0):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "product_uom": self.product.uom_id.id,
                "location_id": src.id,
                "location_dest_id": dest.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.quantity = qty
        move.picked = True
        return move

    # one cost method

    def test_category_with_other_method_is_refused(self):
        self.company.valuation_guard_unique_method = True
        with self.assertRaises(UserError):
            self.env["product.category"].create({"name": "Standard", "property_cost_method": "standard"})
        with self.assertRaises(UserError):
            self.categ.property_valuation = "periodic"

    def test_category_check_is_off_by_default(self):
        categ = self.env["product.category"].create({"name": "Standard", "property_cost_method": "standard"})
        self.assertEqual(categ.property_cost_method, "standard")

    def test_align_saves_costs_and_aligns(self):
        categ = self.env["product.category"].create({"name": "Standard", "property_cost_method": "standard"})
        product = self.env["product.product"].create(
            {"name": "Std Product", "is_storable": True, "categ_id": categ.id, "standard_price": 7.0}
        )
        self.company.valuation_guard_unique_method = True
        self.env["product.category"].action_valuation_guard_align()
        self.assertEqual(categ.property_cost_method, "fifo")
        self.assertFalse(self.env["product.category"].search([])._valuation_guard_misaligned())
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "res.company"), ("res_id", "=", self.company.id), ("name", "like", "valuation_guard")]
        )
        snapshot = json.loads(attachment.raw)
        self.assertEqual(snapshot["standard_price"][str(product.id)], 7.0)
        self.assertEqual(snapshot["categories"][str(categ.id)][1], "standard")

    def test_align_with_nothing_to_align(self):
        self.env["product.category"].search([]).write(
            {"property_cost_method": "fifo", "property_valuation": "real_time"}
        )
        with self.assertRaises(UserError):
            self.env["product.category"].action_valuation_guard_align()

    # no unvalued move

    def test_inventory_gain_without_cost_is_refused(self):
        self.company.valuation_guard_zero_cost = True
        quant = self.env["stock.quant"].create(
            {"product_id": self.product.id, "location_id": self.stock.id, "inventory_quantity": 4.0}
        )
        with self.assertRaises(UserError):
            quant.action_apply_inventory()

    def test_inventory_gain_with_cost_passes(self):
        self.company.valuation_guard_zero_cost = True
        self.product.standard_price = 3.0
        quant = self.env["stock.quant"].create(
            {"product_id": self.product.id, "location_id": self.stock.id, "inventory_quantity": 4.0}
        )
        quant.action_apply_inventory()
        self.assertEqual(self.product.qty_available, 4.0)

    def test_receipt_without_value_is_refused(self):
        self.company.valuation_guard_zero_cost = True
        move = self._move(self.supplier, self.stock)
        with self.assertRaises(UserError):
            move._action_done()

    def test_delivery_without_cost_is_refused(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock, 5.0)
        self.company.valuation_guard_zero_cost = True
        move = self._move(self.stock, self.customer)
        with self.assertRaises(UserError):
            move._action_done()

    def test_delivery_with_cost_passes(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock, 5.0)
        self.product.standard_price = 2.0
        self.company.valuation_guard_zero_cost = True
        move = self._move(self.stock, self.customer)
        move._action_done()
        self.assertEqual(move.state, "done")

    def test_guard_off_lets_moves_through(self):
        move = self._move(self.supplier, self.stock)
        move._action_done()
        self.assertEqual(move.state, "done")

    def test_context_skips_the_guard(self):
        self.company.valuation_guard_zero_cost = True
        move = self._move(self.supplier, self.stock)
        move.with_context(skip_valuation_guard=True)._action_done()
        self.assertEqual(move.state, "done")

    # control lists

    def test_control_lists(self):
        guard = self.env["stock.valuation.guard"]
        without_cost = guard.action_products_without_cost()
        self.assertIn(self.product, self.env["product.product"].search(without_cost["domain"]))
        move = self._move(self.supplier, self.stock)
        move._action_done()
        zero_stock = guard.action_zero_valued_stock()
        self.assertIn(move, self.env["stock.move"].search(zero_stock["domain"]))
        zero_moves = guard.action_zero_valued_moves()
        self.assertIn(move, self.env["stock.move"].search(zero_moves["domain"]))
        self.categ.property_cost_method = "standard"
        misaligned = guard.action_misaligned_categories()
        self.assertIn(self.categ, self.env["product.category"].search(misaligned["domain"]))
