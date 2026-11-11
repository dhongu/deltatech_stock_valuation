from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockReclassification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Account = cls.env["account.account"]
        cls.acc_a = Account.create({"name": "Reclass A", "code": "991001", "account_type": "asset_current"})
        cls.acc_b = Account.create({"name": "Reclass B", "code": "991002", "account_type": "asset_current"})
        cls.acc_c = Account.create({"name": "Reclass C", "code": "991003", "account_type": "expense"})
        cls.journal = cls.env["account.journal"].create({"name": "Reclass test", "code": "RCT", "type": "general"})
        cls.rule = cls.env["stock.reclassification.rule"].create(
            {"account_src_id": cls.acc_a.id, "account_dest_id": cls.acc_b.id}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Reclass Product", "is_storable": True, "standard_price": 10.0}
        )
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.sub = cls.env["stock.location"].create({"name": "Reclass Sub", "location_id": cls.stock.id})
        cls.outside = cls.env["stock.location"].create({"name": "Fixed assets", "usage": "inventory"})
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")

    def _receive(self, product, qty, lot=None):
        move_line_vals = []
        if lot:
            move_line_vals = [
                Command.create(
                    {
                        "product_id": product.id,
                        "product_uom_id": product.uom_id.id,
                        "location_id": self.supplier.id,
                        "location_dest_id": self.stock.id,
                        "lot_id": lot.id,
                        "quantity": qty,
                    }
                )
            ]
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": self.supplier.id,
                "location_dest_id": self.stock.id,
                "move_line_ids": move_line_vals,
            }
        )
        move._action_confirm()
        if not lot:
            move._action_assign()
            move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def _doc(self, qty=4.0, product=None, lot=None, dest=None, rule=None, **kwargs):
        product = product or self.product
        return self.env["stock.reclassification"].create(
            {
                "rule_id": (rule or self.rule).id,
                "location_src_id": self.stock.id,
                "location_dest_id": (dest or self.stock).id,
                "journal_id": self.journal.id,
                "line_ids": [
                    Command.create({"product_id": product.id, "quantity": qty, "lot_id": lot.id if lot else False})
                ],
                **kwargs,
            }
        )

    def _qty(self, product, location):
        return self.env["stock.quant"]._get_available_quantity(product, location, strict=True)

    def _lines(self, move):
        return {line.account_id: (line.debit, line.credit) for line in move.line_ids}

    # --------------------------------------------------------------- the flow

    def test_same_location(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=4)
        self.assertEqual(doc.state, "draft")
        self.assertNotEqual(doc.name, "/")
        doc.action_validate()
        self.assertEqual(doc.state, "done")
        self.assertEqual(doc.picking_id.state, "done")
        self.assertEqual(self.product.qty_available, 10)
        lines = self._lines(doc.account_move_id)
        self.assertEqual(lines[self.acc_b], (40.0, 0.0))
        self.assertEqual(lines[self.acc_a], (0.0, 40.0))
        self.assertEqual(doc.account_move_id.state, "posted")
        self.assertEqual(doc.line_ids.unit_cost, 10.0)
        self.assertEqual(doc.line_ids.value, 40.0)

    def test_transfer_uses_the_internal_type_of_the_warehouse(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=1)
        doc.action_validate()
        self.assertEqual(doc.picking_id.picking_type_id, self.warehouse.int_type_id)

    def test_two_lines_of_the_same_product(self):
        """The moves of a transfer are not merged on confirmation: each line keeps its own move."""
        self._receive(self.product, 10)
        doc = self._doc(qty=4)
        doc.line_ids = [Command.create({"product_id": self.product.id, "quantity": 3.0})]
        doc.action_validate()
        self.assertEqual(doc.state, "done")
        self.assertEqual(len(doc.picking_id.move_ids), 2)
        self.assertEqual(sorted(doc.line_ids.mapped("value")), [30.0, 40.0])
        self.assertEqual(doc.account_move_id.amount_total, 70.0)

    def test_other_location(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=4, dest=self.sub)
        doc.action_validate()
        self.assertEqual(self._qty(self.product, self.sub), 4)
        self.assertEqual(self._qty(self.product, self.stock), 6)
        self.assertEqual(doc.account_move_id.amount_total, 40.0)

    def test_destination_outside_the_stock(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=4, dest=self.outside)
        doc.action_validate()
        self.assertEqual(self.product.qty_available, 6)
        self.assertEqual(self._lines(doc.account_move_id)[self.acc_b], (40.0, 0.0))

    def test_no_automatic_valuation_entry(self):
        categ = self.env["product.category"].create(
            {
                "name": "Reclass real time",
                "property_valuation": "real_time",
                "property_stock_valuation_account_id": self.acc_a.id,
            }
        )
        product = self.env["product.product"].create(
            {"name": "Reclass RT", "is_storable": True, "standard_price": 10.0, "categ_id": categ.id}
        )
        self.outside.valuation_account_id = self.acc_c
        self._receive(product, 10)
        doc = self._doc(qty=4, product=product, dest=self.outside)
        doc.action_validate()
        self.assertFalse(doc.picking_id.move_ids.account_move_id)
        move = self.env["account.move"].search([("ref", "=", doc.name)])
        self.assertEqual(move, doc.account_move_id)

    # ------------------------------------------------------------ validations

    def test_decision_and_reason_required(self):
        self._receive(self.product, 10)
        self.rule.write({"require_decision": True, "require_reason": True})
        doc = self._doc(qty=2)
        with self.assertRaises(UserError):
            doc.action_validate()
        doc.decision_note = "Decision 12/2026"
        with self.assertRaises(UserError):
            doc.action_validate()
        doc.reason = "New destination"
        doc.action_validate()
        self.assertEqual(doc.state, "done")

    def test_not_enough_stock(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=20)
        with self.assertRaises(UserError):
            doc.action_validate()
        self.assertEqual(doc.state, "draft")
        self.assertFalse(self.env["stock.picking"].search([("origin", "=", doc.name)]))

    def test_rule_accounts_must_belong_to_the_company(self):
        other_company = self.env["res.company"].create({"name": "Other reclass company"})
        foreign = self.env["account.account"].create(
            {
                "name": "Foreign",
                "code": "991999",
                "account_type": "asset_current",
                "company_ids": [Command.set(other_company.ids)],
            }
        )
        with self.assertRaises(UserError):
            self.env["stock.reclassification.rule"].create(
                {"company_id": self.company.id, "account_src_id": foreign.id, "account_dest_id": self.acc_b.id}
            )

    def test_archived_rule_refused(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=2)
        self.rule.active = False
        with self.assertRaises(UserError):
            doc.action_validate()

    def test_pair_must_differ_and_be_unique(self):
        with self.assertRaises(Exception):  # noqa: B017 - SQL constraint
            self.env["stock.reclassification.rule"].create(
                {"account_src_id": self.acc_a.id, "account_dest_id": self.acc_a.id}
            )
        with self.assertRaises(Exception):  # noqa: B017 - SQL constraint
            self.env["stock.reclassification.rule"].create(
                {"account_src_id": self.acc_a.id, "account_dest_id": self.acc_b.id}
            )

    def test_serial_number(self):
        product = self.env["product.product"].create(
            {"name": "Reclass Serial", "is_storable": True, "tracking": "serial", "standard_price": 10.0}
        )
        lot1 = self.env["stock.lot"].create({"name": "RS1", "product_id": product.id})
        lot2 = self.env["stock.lot"].create({"name": "RS2", "product_id": product.id})
        self._receive(product, 1, lot=lot1)
        self._receive(product, 1, lot=lot2)
        with self.assertRaises(UserError):
            self._doc(qty=1, product=product).action_validate()
        with self.assertRaises(UserError):
            self._doc(qty=2, product=product, lot=lot1).action_validate()
        doc = self._doc(qty=1, product=product, lot=lot2, dest=self.sub)
        doc.action_validate()
        quant = self.env["stock.quant"].search([("location_id", "=", self.sub.id), ("lot_id", "=", lot2.id)])
        self.assertEqual(quant.quantity, 1)
        self.assertFalse(self.env["stock.quant"].search([("location_id", "=", self.sub.id), ("lot_id", "=", lot1.id)]))

    def test_lot_on_untracked_product_refused(self):
        self._receive(self.product, 10)
        other = self.env["product.product"].create({"name": "Other", "is_storable": True, "tracking": "lot"})
        lot = self.env["stock.lot"].create({"name": "L1", "product_id": other.id})
        doc = self._doc(qty=1)
        doc.line_ids.lot_id = lot
        with self.assertRaises(UserError):
            doc.action_validate()

    # -------------------------------------------------------- vendor bill line

    def _bill(self, qty=5.0, price=12.0):
        partner = self.env["res.partner"].create({"name": "Reclass Vendor"})
        payable = self.env["account.account"].create(
            {"name": "Reclass payable", "code": "991090", "account_type": "liability_payable", "reconcile": True}
        )
        partner.property_account_payable_id = payable
        journal = self.env["account.journal"].create({"name": "Reclass bills", "code": "RCB", "type": "purchase"})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": qty,
                            "price_unit": price,
                            "account_id": self.acc_c.id,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill.invoice_line_ids[0]

    def test_bill_line_quantity_limit_and_price_warning(self):
        self._receive(self.product, 10)
        bill_line = self._bill(qty=5.0, price=12.0)
        first = self._doc(qty=4)
        first.line_ids.invoice_line_id = bill_line
        first.action_validate()
        self.assertTrue(
            first.message_ids.filtered(lambda m: "differs from the price" in (m.body or "")),
            "the cost of the stock (10) differs from the bill price (12): a warning is expected",
        )
        second = self._doc(qty=2)
        second.line_ids.invoice_line_id = bill_line
        with self.assertRaises(UserError):
            second.action_validate()
        third = self._doc(qty=1)
        third.line_ids.invoice_line_id = bill_line
        third.action_validate()
        self.assertEqual(third.state, "done")

    # ---------------------------------------------------------------- cancel

    def test_cancel_done_reverses_transfer_and_entry(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=4, dest=self.sub)
        doc.action_validate()
        doc.action_cancel()
        self.assertEqual(doc.state, "cancel")
        self.assertEqual(doc.reverse_picking_id.state, "done")
        self.assertEqual(self._qty(self.product, self.sub), 0)
        self.assertEqual(self._qty(self.product, self.stock), 10)
        self.assertEqual(doc.reverse_account_move_id.state, "posted")
        balance = sum(
            self.env["account.move.line"]
            .search([("account_id", "=", self.acc_b.id), ("parent_state", "=", "posted")])
            .mapped("balance")
        )
        self.assertEqual(balance, 0.0)

    def test_cancel_draft(self):
        doc = self._doc(qty=4)
        doc.action_cancel()
        self.assertEqual(doc.state, "cancel")
        self.assertFalse(doc.picking_id)

    def test_cancel_hook_can_refuse(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=4)
        doc.action_validate()
        model = type(doc)
        original = model._check_before_cancel

        def refuse(self):
            raise UserError(self.env._("refused"))

        model._check_before_cancel = refuse
        try:
            with self.assertRaises(UserError):
                doc.action_cancel()
        finally:
            model._check_before_cancel = original
        self.assertEqual(doc.state, "done")

    def test_validated_document_cannot_be_deleted(self):
        self._receive(self.product, 10)
        doc = self._doc(qty=1)
        doc.action_validate()
        with self.assertRaises(UserError):
            doc.unlink()

    # ---------------------------------------------------------------- groups

    def test_rules_menu_follows_the_configuration_group(self):
        stock_group = self.env.ref("stock.group_stock_user")
        reclass_group = self.env.ref("deltatech_stock_reclass.group_stock_reclassification_user")
        manager_group = self.env.ref("deltatech_stock_reclass.group_stock_reclassification_manager")
        menu_rules = self.env.ref("deltatech_stock_reclass.menu_stock_reclassification_rule")
        menu_docs = self.env.ref("deltatech_stock_reclass.menu_stock_reclassification")
        user = self.env["res.users"].create(
            {"name": "Reclass user", "login": "reclass_menu_user", "group_ids": [Command.set([reclass_group.id])]}
        )

        def visible(menu):
            return bool(menu.with_user(user)._filter_visible_menus())

        self.assertTrue(visible(menu_docs))
        self.assertFalse(visible(menu_rules))
        # the configuration group alone (no Inventory manager role) must see the rules menu
        user.group_ids = [Command.set([manager_group.id])]
        self.assertTrue(visible(menu_rules))
        self.assertIn(stock_group, user.all_group_ids)

    def test_groups(self):
        stock_group = self.env.ref("stock.group_stock_user")
        user = self.env["res.users"].create(
            {"name": "Stock only", "login": "stock_only_rcl", "group_ids": [Command.set([stock_group.id])]}
        )
        with self.assertRaises(AccessError):
            self._doc().with_user(user).read(["name"])
        reclass_group = self.env.ref("deltatech_stock_reclass.group_stock_reclassification_user")
        user.group_ids = [Command.link(reclass_group.id)]
        self.assertTrue(self._doc().with_user(user).read(["name"]))
        with self.assertRaises(AccessError):
            self.env["stock.reclassification.rule"].with_user(user).create(
                {"account_src_id": self.acc_b.id, "account_dest_id": self.acc_c.id}
            )
        manager_group = self.env.ref("deltatech_stock_reclass.group_stock_reclassification_manager")
        user.group_ids = [Command.link(manager_group.id)]
        rule = (
            self.env["stock.reclassification.rule"]
            .with_user(user)
            .create({"account_src_id": self.acc_b.id, "account_dest_id": self.acc_c.id})
        )
        self.assertTrue(rule)
