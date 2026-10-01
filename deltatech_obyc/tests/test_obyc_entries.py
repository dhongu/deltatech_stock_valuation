# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Notele contabile OBYC (conturi Dr/Cr, sume, cantități semnate) pe scenariile de bază:
# recepție, livrare, retur de la client (negru și storno). Aceleași valori ca în 19 —
# în 20 `stock.move.value` e negativ pe ieșiri, nota OBYC trebuie să rămână pozitivă.

from odoo import Command
from odoo.tests import tagged

from .test_common import TestCommon


@tagged("post_install", "-at_install")
class TestObycEntries(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_stock_valuation = cls.env["account.account"].create(
            {"name": "Stock Valuation Cat", "code": "SVC003", "account_type": "asset_current"}
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
        cls.account_customer = cls.env["account.account"].create(
            {"name": "Test Customer Return Account", "code": "TCR001", "account_type": "asset_current"}
        )
        # recepție: Dr valuation / Cr src; livrare (doar acc_dest): Dr dest / Cr valuation;
        # retur de la client: Dr valuation / Cr src
        for key, src, dest in [
            ("stock_receipt", cls.account_src, False),
            ("stock_delivery", False, cls.account_dest),
            ("return_from_customer", cls.account_customer, False),
        ]:
            cls.env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": cls.env.company.id,
                    "acc_src_id": src and src.id,
                    "acc_dest_id": dest and dest.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

    def _picking(self, picking_type, location, location_dest, qty):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "uom_id": self.product.uom_id.id,
                            "location_id": location.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                ],
            }
        )
        self._validate(picking)
        return picking

    def _validate(self, picking):
        picking.action_confirm()
        picking.move_ids._set_quantity_done(picking.move_ids[0].product_uom_qty)
        picking.with_context(demo_mode=True).button_validate()

    def _lines(self, picking):
        account_move = picking.move_ids.account_move_id
        self.assertEqual(len(account_move), 1)
        self.assertEqual(account_move.state, "posted")
        self.assertEqual(account_move.journal_id, self.stock_journal)
        return account_move.line_ids.sorted(lambda line: (line.account_id.code, line.debit, line.credit))

    def _receipt(self, qty):
        return self._picking(self.picking_type_in, self.supplier_location, self.stock_location, qty)

    def _delivery(self, qty):
        return self._picking(self.picking_type_out, self.stock_location, self.customer_location, qty)

    def _customer_return(self, picking, qty):
        return_picking = picking._create_return()
        return_picking.move_ids.product_uom_qty = qty
        self._validate(return_picking)
        return return_picking

    def test_01_receipt(self):
        lines = self._lines(self._receipt(10.0))
        self.assertRecordValues(
            lines,
            [
                {"account_id": self.account_src.id, "debit": 0.0, "credit": 1000.0, "quantity": -10.0},
                {"account_id": self.account_valuation.id, "debit": 1000.0, "credit": 0.0, "quantity": 10.0},
            ],
        )

    def test_02_delivery(self):
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertAlmostEqual(abs(delivery.move_ids.value), 400.0)
        self.assertRecordValues(
            self._lines(delivery),
            [
                {"account_id": self.account_dest.id, "debit": 400.0, "credit": 0.0, "quantity": 4.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 400.0, "quantity": -4.0},
            ],
        )

    def test_03_customer_return(self):
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertRecordValues(
            self._lines(self._customer_return(delivery, 1.0)),
            [
                {"account_id": self.account_customer.id, "debit": 0.0, "credit": 100.0, "quantity": -1.0},
                {"account_id": self.account_valuation.id, "debit": 100.0, "credit": 0.0, "quantity": 1.0},
            ],
        )

    def test_04_customer_return_storno(self):
        self.env.company.account_storno = True
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertRecordValues(
            self._lines(self._customer_return(delivery, 1.0)),
            [
                {"account_id": self.account_customer.id, "debit": -100.0, "credit": 0.0, "quantity": 1.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": -100.0, "quantity": -1.0},
            ],
        )
