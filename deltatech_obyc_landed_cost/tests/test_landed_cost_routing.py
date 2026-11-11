# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Landed cost on OBYC: standard note and class 6 credit routed through the intermediary account.

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.deltatech_obyc.tests.test_common import TestCommon


@tagged("post_install", "-at_install")
class TestLandedCostRouting(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        account = cls.env["account.account"]
        cls.account_stock = account.create({"name": "Stock 371", "code": "TLC371", "account_type": "asset_current"})
        cls.account_624 = account.create({"name": "Transport 624", "code": "624TLC", "account_type": "expense"})
        cls.account_609 = account.create({"name": "Discount 609", "code": "609TLC", "account_type": "expense"})
        cls.account_408 = account.create({"name": "Invoices 408", "code": "TLC408", "account_type": "asset_current"})
        cls.account_inter = account.create({"name": "Inter 482", "code": "TLC482", "account_type": "asset_current"})
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_stock.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product.standard_price = 100.0
        for key, src, dest in [("stock_receipt", cls.account_src, False), ("landed_cost", False, False)]:
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
        cls.cost_product = cls.env["product.product"].create(
            {"name": "Transport", "type": "service", "landed_cost_ok": True}
        )

    def _receipt(self, qty):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.env.ref("stock.picking_type_in").id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.env.ref("stock.stock_location_stock").id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.env.ref("stock.stock_location_suppliers").id,
                            "location_dest_id": self.env.ref("stock.stock_location_stock").id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids._set_quantity_done(qty)
        picking.with_context(demo_mode=True).button_validate()
        return picking

    def _landed_cost(self, picking, account, amount=50.0):
        landed = self.env["stock.landed.cost"].create(
            {
                "picking_ids": [Command.set(picking.ids)],
                "account_journal_id": self.stock_journal.id,
                "cost_lines": [
                    Command.create(
                        {
                            "name": "Transport",
                            "product_id": self.cost_product.id,
                            "price_unit": amount,
                            "split_method": "by_quantity",
                            "account_id": account.id,
                        }
                    )
                ],
            }
        )
        landed.compute_landed_cost()
        landed.button_validate()
        return landed

    def _dr_cr(self, move):
        return sorted((line.account_id.code, line.debit, line.credit) for line in move.line_ids)

    def _enable_routing(self):
        self.env.company.write(
            {"landed_cost_method": "intermediary", "landed_cost_intermediary_account_id": self.account_inter.id}
        )

    def test_01_standard_class6_direct(self):
        """Standard method: Dr stock (OBYC rule) / Cr class 6, 50 lei, on the cost journal."""
        landed = self._landed_cost(self._receipt(10.0), self.account_624)
        move = landed.account_move_id
        self.assertEqual(move.journal_id, self.stock_journal)
        self.assertEqual(self._dr_cr(move), [("624TLC", 0.0, 50.0), ("TVA001", 50.0, 0.0)])

    def test_02_intermediary_class6_routed(self):
        """Intermediary method: Dr stock / Cr 482 and Dr 482 / Cr class 6, same amount."""
        self._enable_routing()
        move = self._landed_cost(self._receipt(10.0), self.account_624).account_move_id
        self.assertEqual(move.journal_id, self.stock_journal)
        self.assertEqual(
            self._dr_cr(move),
            [("624TLC", 0.0, 50.0), ("TLC482", 0.0, 50.0), ("TLC482", 50.0, 0.0), ("TVA001", 50.0, 0.0)],
        )
        self.assertEqual(move.state, "posted")

    def test_03_class_609_not_routed(self):
        self._enable_routing()
        move = self._landed_cost(self._receipt(10.0), self.account_609).account_move_id
        self.assertEqual(self._dr_cr(move), [("609TLC", 0.0, 50.0), ("TVA001", 50.0, 0.0)])

    def test_04_non_class6_not_routed(self):
        self._enable_routing()
        move = self._landed_cost(self._receipt(10.0), self.account_408).account_move_id
        self.assertEqual(self._dr_cr(move), [("TLC408", 0.0, 50.0), ("TVA001", 50.0, 0.0)])

    def test_05_negative_cost_class6(self):
        """A negative cost reverses the entry; the debit on class 6 is not rerouted."""
        self._enable_routing()
        move = self._landed_cost(self._receipt(10.0), self.account_624, amount=-50.0).account_move_id
        self.assertEqual(self._dr_cr(move), [("624TLC", 50.0, 0.0), ("TVA001", 0.0, 50.0)])

    def test_06_method_standard_ignores_account(self):
        self.env.company.landed_cost_intermediary_account_id = self.account_inter
        move = self._landed_cost(self._receipt(10.0), self.account_624).account_move_id
        self.assertEqual(self._dr_cr(move), [("624TLC", 0.0, 50.0), ("TVA001", 50.0, 0.0)])

    def test_07_value_increases(self):
        """The landed cost raises the receipt value by 50 lei (1000 -> 1050) in both methods."""
        self._enable_routing()
        receipt = self._receipt(10.0)
        self._landed_cost(receipt, self.account_624)
        self.assertAlmostEqual(receipt.move_ids.value, 1050.0)

    def test_08_intermediary_account_not_class_6(self):
        """The intermediary account cannot be a class 6 account (it would be on both debit and credit)."""
        with self.assertRaises(ValidationError):
            self.env.company.landed_cost_intermediary_account_id = self.account_624
