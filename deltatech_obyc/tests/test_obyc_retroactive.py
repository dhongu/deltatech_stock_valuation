# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Odoo 20 reia valorizarea (`stock.move._set_value(recompute_date=...)`) și rescrie
# `value` pe ieșirile deja validate când o intrare se mută în trecut, când se editează
# cantitatea unei mișcări validate sau când factura de furnizor reevaluează o intrare.
# Notele OBYC sunt postate din `value` la validare și nu se rescriu, deci pentru
# produsele OBYC valoarea ieșirilor rămâne cea din momentul validării (ca în 19).
# Produsele fără clasă de evaluare păstrează comportamentul standard 20.

from datetime import timedelta

from odoo import Command, fields
from odoo.tests import Form, tagged

from .test_common import TestCommon


@tagged("post_install", "-at_install")
class TestObycRetroactiveRecompute(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_stock_valuation = cls.env["account.account"].create(
            {"name": "Stock Valuation Cat", "code": "SVC004", "account_type": "asset_current"}
        )
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        # fără standard_price setat aici: ar crea un istoric de cost (product.value)
        # datat după intrarea mutată în trecut, care ar reseta costul mediu la reluare
        # același flux, produs fără clasă de evaluare OBYC (comportament standard 20)
        cls.product_std = cls.env["product.product"].create(
            {
                "name": "Test Product Standard",
                "is_storable": True,
                "categ_id": cls.product_category.id,
            }
        )
        for key in ("stock_receipt", "stock_delivery"):
            cls.env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": cls.env.company.id,
                    "acc_src_id": cls.account_src.id if key == "stock_receipt" else False,
                    "acc_dest_id": cls.account_dest.id if key == "stock_delivery" else False,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )
        cls.account_payable = cls.env["account.account"].create(
            {"name": "Test Payable", "code": "TPAY01", "account_type": "liability_payable", "reconcile": True}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Vendor", "property_account_payable_id": cls.account_payable.id}
        )
        cls.purchase_journal = cls.env["account.journal"].create(
            {"name": "Test Purchase Journal", "code": "TPJ1", "type": "purchase"}
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

    def _purchase(self, product, qty, price):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [Command.create({"product_id": product.id, "product_qty": qty, "price_unit": price})],
            }
        )
        order.button_confirm()
        picking = order.picking_ids
        picking.move_ids._set_quantity_done(qty)
        picking.with_context(demo_mode=True).button_validate()
        self.assertEqual(picking.state, "done")
        return order

    def _deliver(self, product, qty):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "uom_id": product.uom_id.id,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids._set_quantity_done(qty)
        picking.with_context(demo_mode=True).button_validate()
        self.assertEqual(picking.state, "done")
        return picking.move_ids

    def _bill(self, order, price):
        order.action_create_invoice()
        bill = order.invoice_ids
        with Form(bill) as bill_form:
            bill_form.invoice_date = fields.Date.today()
            with bill_form.invoice_line_ids.edit(0) as line:
                line.price_unit = price
        bill.action_post()
        return bill

    def _entry_amount(self, move):
        return sum(move.account_move_id.line_ids.mapped("debit"))

    # 1) intrare mutată în trecut, înaintea unei ieșiri deja validate
    def _scenario_backdated_receipt(self, product):
        self._purchase(product, 10.0, 100.0)
        delivery = self._deliver(product, 5.0)
        order = self._purchase(product, 10.0, 200.0)
        order.picking_ids.move_ids.date = delivery.date - timedelta(hours=1)
        return delivery

    def test_01_backdated_receipt_keeps_obyc_out_value(self):
        delivery = self._scenario_backdated_receipt(self.product)
        self.assertAlmostEqual(delivery.value, -500.0)
        self.assertAlmostEqual(self._entry_amount(delivery), 500.0)

    def test_01_backdated_receipt_standard_product(self):
        delivery = self._scenario_backdated_receipt(self.product_std)
        # comportament standard 20: la livrare costul mediu devine (1000 + 2000) / 20
        self.assertAlmostEqual(delivery.value, -750.0)

    # 2) cantitatea unei intrări validate editată după o ieșire
    def _scenario_edit_done_quantity(self, product):
        order_1 = self._purchase(product, 10.0, 100.0)
        self._purchase(product, 10.0, 200.0)
        delivery = self._deliver(product, 5.0)
        order_1.picking_ids.move_ids.move_line_ids.quantity = 20.0
        return order_1.picking_ids.move_ids, delivery

    def test_02_edit_done_quantity_keeps_obyc_out_value(self):
        receipt, delivery = self._scenario_edit_done_quantity(self.product)
        self.assertAlmostEqual(receipt.value, 2000.0)
        self.assertAlmostEqual(delivery.value, -750.0)
        self.assertAlmostEqual(self._entry_amount(delivery), 750.0)

    def test_02_edit_done_quantity_standard_product(self):
        receipt, delivery = self._scenario_edit_done_quantity(self.product_std)
        self.assertAlmostEqual(receipt.value, 2000.0)
        # comportament standard 20: (2000 + 2000) / 30 * 5
        self.assertAlmostEqual(delivery.value, -666.67, places=2)

    # 3) factura de furnizor cu alt preț, după livrare
    def _scenario_vendor_bill(self, product):
        order = self._purchase(product, 10.0, 100.0)
        delivery = self._deliver(product, 5.0)
        self._bill(order, 120.0)
        return order.picking_ids.move_ids, delivery

    def test_03_vendor_bill_keeps_obyc_out_value(self):
        receipt, delivery = self._scenario_vendor_bill(self.product)
        self.assertAlmostEqual(receipt.value, 1200.0)
        self.assertAlmostEqual(delivery.value, -500.0)
        self.assertAlmostEqual(self._entry_amount(delivery), 500.0)

    def test_03_vendor_bill_standard_product(self):
        receipt, delivery = self._scenario_vendor_bill(self.product_std)
        self.assertAlmostEqual(receipt.value, 1200.0)
        # comportament standard 20: ieșirea e reevaluată la noul cost
        self.assertAlmostEqual(delivery.value, -600.0)

    # setarea companiei `valuation_keep_move_value` dezactivată: produsele OBYC urmează
    # reluarea standard 20 (aceleași valori ca produsul fără clasă de evaluare)
    def _disable_keep_move_value(self):
        self.env.company.valuation_keep_move_value = False

    def test_04_backdated_receipt_obyc_without_keep_setting(self):
        self._disable_keep_move_value()
        delivery = self._scenario_backdated_receipt(self.product)
        self.assertAlmostEqual(delivery.value, -750.0)

    def test_05_edit_done_quantity_obyc_without_keep_setting(self):
        self._disable_keep_move_value()
        receipt, delivery = self._scenario_edit_done_quantity(self.product)
        self.assertAlmostEqual(receipt.value, 2000.0)
        self.assertAlmostEqual(delivery.value, -666.67, places=2)

    def test_06_vendor_bill_obyc_without_keep_setting(self):
        self._disable_keep_move_value()
        receipt, delivery = self._scenario_vendor_bill(self.product)
        self.assertAlmostEqual(receipt.value, 1200.0)
        self.assertAlmostEqual(delivery.value, -600.0)
