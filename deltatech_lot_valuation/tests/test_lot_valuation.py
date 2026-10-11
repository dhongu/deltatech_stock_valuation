# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "deltatech_lot_valuation")
class TestLotValuation(TransactionCase):
    """Valorizarea ieșirilor, a quanturilor și a recepțiilor pe loturi cu prețuri diferite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.vendor = cls.env["res.partner"].create({"name": "Vendor"})
        cls.customer = cls.env["res.partner"].create({"name": "Customer"})

    def _product(self, method, tracking="lot"):
        categ = self.env["product.category"].create({"name": "Cat %s" % method})
        categ.property_cost_method = method
        return self.env["product.product"].create(
            {
                "name": "Prod %s %s" % (method, tracking),
                "is_storable": True,
                "tracking": tracking,
                "categ_id": categ.id,
                "standard_price": 1.0,
            }
        )

    def _receive(self, product, lots_qty, price):
        """lots_qty: {nume_lot: cantitate}; recepție de la furnizor la preț dat."""
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    Command.create(
                        {"product_id": product.id, "product_qty": sum(lots_qty.values()), "price_unit": price}
                    )
                ],
            }
        )
        po.button_confirm()
        picking = po.picking_ids
        move = picking.move_ids
        move.move_line_ids.unlink()
        move.write(
            {
                "move_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "lot_name": name,
                            "quantity": qty,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "picking_id": picking.id,
                        }
                    )
                    for name, qty in lots_qty.items()
                ]
            }
        )
        move.picked = True
        picking.button_validate()
        return self.env["stock.lot"].search([("name", "in", list(lots_qty)), ("product_id", "=", product.id)])

    def _deliver(self, product, lot_qty):
        """lot_qty: lista de (lot, cantitate) livrate clientului."""
        location = self.warehouse.lot_stock_id
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": location.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "partner_id": self.customer.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": sum(qty for _lot, qty in lot_qty),
                            "location_id": location.id,
                            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                            "move_line_ids": [
                                Command.create(
                                    {
                                        "product_id": product.id,
                                        "lot_id": lot.id,
                                        "quantity": qty,
                                        "location_id": location.id,
                                        "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                                    }
                                )
                                for lot, qty in lot_qty
                            ],
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.picked = True
        picking.button_validate()
        return picking.move_ids

    def test_receipt_sets_lot_prices(self):
        for method in ("average", "fifo"):
            with self.subTest(method=method):
                product = self._product(method)
                lot = self._receive(product, {"A-%s" % method: 10}, 12.5)
                self.assertAlmostEqual(lot.unit_price, 12.5)
                self.assertAlmostEqual(lot.input_price, 12.5)
                self.assertAlmostEqual(lot.inventory_value, 125.0)
                self.assertTrue(lot.input_date)

    def test_delivery_is_valued_at_lot_prices(self):
        for method in ("average", "fifo"):
            with self.subTest(method=method):
                product = self._product(method)
                lot_a = self._receive(product, {"A-%s" % method: 10}, 10.0)
                lot_b = self._receive(product, {"B-%s" % method: 6}, 20.0)
                move = self._deliver(product, [(lot_a, 3), (lot_b, 2)])
                self.assertAlmostEqual(move.value, 3 * 10.0 + 2 * 20.0)

    def test_quant_value_follows_lot_price(self):
        product = self._product("average")
        lot_a = self._receive(product, {"A-q": 10}, 10.0)
        lot_b = self._receive(product, {"B-q": 6}, 20.0)
        self._deliver(product, [(lot_a, 3)])
        self.env.invalidate_all()
        quant_a = lot_a.quant_ids.filtered(lambda q: q.location_id == self.warehouse.lot_stock_id)
        quant_b = lot_b.quant_ids.filtered(lambda q: q.location_id == self.warehouse.lot_stock_id)
        self.assertAlmostEqual(quant_a.value, 7 * 10.0)
        self.assertAlmostEqual(quant_a.price_unit, 10.0)
        self.assertAlmostEqual(quant_b.value, 6 * 20.0)

    def test_lot_without_price_falls_back_to_core_value(self):
        product = self._product("average")
        lot = self._receive(product, {"A-nop": 10}, 10.0)
        lot.write({"unit_price": 0, "input_price": 0, "inventory_value": 0})
        move = self._deliver(product, [(lot, 4)])
        # costul calculat de nucleu pentru produs, nu 0
        self.assertAlmostEqual(move.value, 4 * 10.0)

    def test_serial_value_from_inventory_value(self):
        product = self._product("average", tracking="serial")
        lots = self._receive(product, {"S1": 1, "S2": 1}, 100.0)
        lots.filtered(lambda l: l.name == "S2").write({"inventory_value": 300.0, "unit_price": 300.0})
        move = self._deliver(product, [(lots.filtered(lambda l: l.name == "S2"), 1)])
        self.assertAlmostEqual(move.value, 300.0)

    def test_stock_value_report_follows_lots(self):
        """Raportul de evaluare pe conturi citește valoarea de pe loturi, nu totalul FIFO al produsului."""
        company = self.env.company
        if not company.chart_template:
            self.env["account.chart.template"]._load("generic_coa", company, install_demo=False)
        for method in ("fifo", "average"):
            with self.subTest(method=method):
                product = self._product(method)
                product.categ_id.property_valuation = "real_time"
                plain = self.env["product.product"].create(
                    {"name": "Fara loturi %s" % method, "is_storable": True, "categ_id": product.categ_id.id}
                )
                lot_a = self._receive(product, {"RA-%s" % method: 5}, 10.0)
                lot_b = self._receive(product, {"RB-%s" % method: 5}, 20.0)
                self._deliver(product, [(lot_b, 5)])
                account = product.product_tmpl_id.get_product_accounts()["stock_valuation"]
                by_product = company._get_accounts_by_product(product | plain)
                core_total = product.total_value
                self.assertNotAlmostEqual(core_total, 50.0, msg="scenariul trebuie să diferențieze nucleul de loturi")
                self.env.invalidate_all()
                for at_date in (None, fields.Datetime.now()):
                    value = company.stock_value(by_product, at_date=at_date)
                    self.assertAlmostEqual(value[account], 50.0 + plain.total_value, msg=str(at_date))
                self.assertEqual(lot_a.product_qty, 5)

    def test_second_receipt_of_lot_with_stock_at_same_price_keeps_unit_price(self):
        product = self._product("average")
        lot = self._receive(product, {"SAME": 5}, 10.0)
        self._receive(product, {"SAME": 5}, 10.0)
        self.assertEqual(lot.product_qty, 10)
        self.assertAlmostEqual(lot.unit_price, 10.0)
        self.assertAlmostEqual(lot.inventory_value, 100.0)

    def test_second_receipt_of_lot_with_stock_at_other_price_is_refused(self):
        product = self._product("average")
        lot = self._receive(product, {"DIFF": 5}, 10.0)
        with self.assertRaises(UserError):
            with self.cr.savepoint():
                self._receive(product, {"DIFF": 5}, 12.0)
        self.assertEqual(lot.product_qty, 5)
        self.assertAlmostEqual(lot.unit_price, 10.0)

    def test_second_receipt_of_emptied_lot_sets_new_price(self):
        product = self._product("average")
        lot = self._receive(product, {"EMPTY": 5}, 10.0)
        self._deliver(product, [(lot, 5)])
        self._receive(product, {"EMPTY": 5}, 12.0)
        self.assertAlmostEqual(lot.unit_price, 12.0)
        self.assertAlmostEqual(lot.input_price, 12.0)

    def test_landed_cost_adjusted_price_does_not_block_same_supplier_price(self):
        product = self._product("average")
        lot = self._receive(product, {"ADJ": 5}, 10.0)
        lot.unit_price = 11.0  # preț ajustat ulterior (landed cost / factură); input_price rămâne 10
        self._receive(product, {"ADJ": 5}, 10.0)
        self.assertAlmostEqual(lot.unit_price, 11.0)

