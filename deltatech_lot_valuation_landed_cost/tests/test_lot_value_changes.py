# © 2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "deltatech_lot_valuation_landed_cost")
class TestLotValueChanges(TransactionCase):
    """Modificările valorii unei recepții cu loturi (landed cost, factură, preț PO) ajung în prețul lotului."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not cls.company.chart_template:
            cls.env["account.chart.template"]._load("generic_coa", cls.company, install_demo=False)
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.vendor = cls.env["res.partner"].create({"name": "Vendor"})
        cls.customer = cls.env["res.partner"].create({"name": "Customer"})
        categ = cls.env["product.category"].create({"name": "Cat lot"})
        categ.property_cost_method = "fifo"
        cls.product = cls.env["product.product"].create(
            {
                "name": "Produs cu loturi",
                "is_storable": True,
                "tracking": "lot",
                "categ_id": categ.id,
                "standard_price": 1.0,
            }
        )
        cls.service_lc = cls.env["product.product"].create(
            {"name": "Cost transport", "type": "service", "landed_cost_ok": True}
        )

    def _receive_three_lots(self):
        """6 buc în 3 loturi (2/1/3) la 100 buc, ca scenariul real din tichetul 9304."""
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [Command.create({"product_id": self.product.id, "product_qty": 6, "price_unit": 100.0})],
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
                            "product_id": self.product.id,
                            "lot_name": name,
                            "quantity": qty,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "picking_id": picking.id,
                        }
                    )
                    for name, qty in (("LOT-A", 2), ("LOT-B", 1), ("LOT-C", 3))
                ]
            }
        )
        move.picked = True
        picking.button_validate()
        lots = self.env["stock.lot"].search([("product_id", "=", self.product.id)], order="name")
        self.assertEqual(len(lots), 3)
        return po, picking, lots

    def _deliver(self, lot, qty):
        location = self.warehouse.lot_stock_id
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": location.id,
                "location_dest_id": customers.id,
                "partner_id": self.customer.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "location_id": location.id,
                            "location_dest_id": customers.id,
                            "move_line_ids": [
                                Command.create(
                                    {
                                        "product_id": self.product.id,
                                        "lot_id": lot.id,
                                        "quantity": qty,
                                        "location_id": location.id,
                                        "location_dest_id": customers.id,
                                    }
                                )
                            ],
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.picked = True
        picking.button_validate()

    def _landed_cost(self, picking, amount):
        lc_form = Form(self.env["stock.landed.cost"])
        lc_form.picking_ids.add(picking)
        with lc_form.cost_lines.new() as cost_line:
            cost_line.product_id = self.service_lc
            cost_line.price_unit = amount
        lc = lc_form.save()
        lc.compute_landed_cost()
        lc.button_validate()
        return lc

    def _bill(self, po, price_unit):
        bill = self.env["account.move"].browse(po.action_create_invoice()["res_id"])
        bill.invoice_date = bill.date
        bill.invoice_line_ids.price_unit = price_unit
        bill.action_post()
        return bill

    def _notes(self, lot):
        return lot.message_ids.filtered(lambda m: "Valoarea recepției" in (m.body or ""))

    def test_plain_receipt_does_not_post_value_change(self):
        _po, _picking, lots = self._receive_three_lots()
        for lot in lots:
            self.assertAlmostEqual(lot.unit_price, 100.0)
            self.assertFalse(self._notes(lot), "prima valorizare nu este o modificare de valoare")

    def test_landed_cost_updates_lot_prices(self):
        _po, picking, lots = self._receive_three_lots()
        self._landed_cost(picking, 60.0)
        # 60 / 6 buc = 10 pe bucată, indiferent de lot
        qty_by_lot = {"LOT-A": 2, "LOT-B": 1, "LOT-C": 3}
        for lot in lots:
            qty = qty_by_lot[lot.name]
            self.assertAlmostEqual(lot.unit_price, 110.0, places=2, msg=lot.name)
            self.assertAlmostEqual(lot.inventory_value, 110.0 * qty, places=2, msg=lot.name)
            self.assertTrue(self._notes(lot), "lipsește nota din chatter-ul lotului %s" % lot.name)

    def test_landed_cost_skips_fully_consumed_lot(self):
        _po, picking, lots = self._receive_three_lots()
        lot_a = lots.filtered(lambda lot: lot.name == "LOT-A")
        self._deliver(lot_a, 2)
        self.assertEqual(lot_a.product_qty, 0)
        self._landed_cost(picking, 60.0)
        self.assertAlmostEqual(lot_a.unit_price, 100.0, places=2, msg="lotul epuizat nu primește cost")
        self.assertFalse(self._notes(lot_a))
        # pe cele 4 buc rămase se repartizează 4 × 10
        lot_c = lots.filtered(lambda lot: lot.name == "LOT-C")
        self.assertAlmostEqual(lot_c.unit_price, 110.0, places=2)

    def test_vendor_bill_higher_price_raises_lot_prices(self):
        po, _picking, lots = self._receive_three_lots()
        self._bill(po, 110.0)
        for lot in lots:
            self.assertAlmostEqual(lot.unit_price, 110.0, places=2, msg=lot.name)
            self.assertTrue(self._notes(lot))

    def test_vendor_bill_lower_price_lowers_lot_prices(self):
        po, _picking, lots = self._receive_three_lots()
        self._bill(po, 90.0)
        for lot in lots:
            self.assertAlmostEqual(lot.unit_price, 90.0, places=2, msg=lot.name)

    def test_vendor_bill_after_partial_delivery(self):
        po, _picking, lots = self._receive_three_lots()
        lot_a = lots.filtered(lambda lot: lot.name == "LOT-A")
        self._deliver(lot_a, 2)
        self._bill(po, 110.0)
        self.assertAlmostEqual(lot_a.unit_price, 100.0, places=2, msg="lotul livrat rămâne la prețul vechi")
        for lot in lots - lot_a:
            self.assertAlmostEqual(lot.unit_price, 110.0, places=2, msg=lot.name)

    def test_bill_at_same_price_changes_nothing(self):
        po, _picking, lots = self._receive_three_lots()
        self._bill(po, 100.0)
        for lot in lots:
            self.assertAlmostEqual(lot.unit_price, 100.0, places=2, msg=lot.name)
            self.assertFalse(self._notes(lot))

    def test_quantity_change_keeps_unit_price(self):
        _po, picking, lots = self._receive_three_lots()
        lot_c = lots.filtered(lambda lot: lot.name == "LOT-C")
        move_line = picking.move_line_ids.filtered(lambda ml: ml.lot_id == lot_c)
        move_line.quantity = 4
        self.assertAlmostEqual(lot_c.unit_price, 100.0, places=2)
        self.assertFalse(self._notes(lot_c))

    def _real_time_product(self, method):
        categ = self.env["product.category"].create({"name": "Cat rt %s" % method})
        categ.property_cost_method = method
        categ.property_valuation = "real_time"
        return self.env["product.product"].create(
            {
                "name": "Produs rt %s" % method,
                "is_storable": True,
                "tracking": "lot",
                "categ_id": categ.id,
                "standard_price": 1.0,
            }
        )

    def _receive_one_lot(self, product, lot_name, qty, price):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [Command.create({"product_id": product.id, "product_qty": qty, "price_unit": price})],
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
                            "lot_name": lot_name,
                            "quantity": qty,
                            "location_id": move.location_id.id,
                            "location_dest_id": move.location_dest_id.id,
                            "picking_id": picking.id,
                        }
                    )
                ]
            }
        )
        move.picked = True
        picking.button_validate()
        return picking, self.env["stock.lot"].search([("name", "=", lot_name), ("product_id", "=", product.id)])

    def _stock_debit(self, landed_cost, product):
        stock_account = product.product_tmpl_id.get_product_accounts()["stock_valuation"]
        lines = landed_cost.account_move_id.line_ids.filtered(lambda line: line.account_id == stock_account)
        return sum(lines.mapped("balance"))

    def test_landed_cost_follows_real_stock_when_other_lot_delivered(self):
        """R1 (lot A) și R2 (lot B); se livrează lotul B, deci nu în ordinea FIFO. Landed cost-ul pe R1
        se capitalizează în lotul A, care a rămas în stoc, și în contul de stoc."""
        for method in ("fifo", "average"):
            with self.subTest(method=method):
                self.product = self._real_time_product(method)
                picking_1, lot_a = self._receive_one_lot(self.product, "A-%s" % method, 5, 10.0)
                _picking_2, lot_b = self._receive_one_lot(self.product, "B-%s" % method, 5, 20.0)
                self._deliver(lot_b, 5)
                landed_cost = self._landed_cost(picking_1, 50.0)
                self.assertAlmostEqual(lot_a.unit_price, 20.0, places=2)
                self.assertAlmostEqual(lot_a.inventory_value, 100.0, places=2)
                self.assertAlmostEqual(self._stock_debit(landed_cost, self.product), 50.0, places=2)
                self.env.invalidate_all()
                quant = lot_a.quant_ids.filtered(lambda q: q.location_id == self.warehouse.lot_stock_id)
                self.assertAlmostEqual(quant.value, 100.0, places=2)

    def test_landed_cost_on_receipt_whose_lot_was_delivered(self):
        """Landed cost-ul pe R2, al cărei lot (B) a fost livrat, nu capitalizează nimic: nici în
        lotul A rămas din R1, nici în contul de stoc."""
        for method in ("fifo", "average"):
            with self.subTest(method=method):
                self.product = self._real_time_product(method)
                _picking_1, lot_a = self._receive_one_lot(self.product, "A2-%s" % method, 5, 10.0)
                picking_2, lot_b = self._receive_one_lot(self.product, "B2-%s" % method, 5, 20.0)
                self._deliver(lot_b, 5)
                landed_cost = self._landed_cost(picking_2, 50.0)
                self.assertAlmostEqual(lot_a.unit_price, 10.0, places=2)
                self.assertAlmostEqual(lot_b.unit_price, 20.0, places=2)
                self.assertAlmostEqual(self._stock_debit(landed_cost, self.product), 0.0, places=2)

