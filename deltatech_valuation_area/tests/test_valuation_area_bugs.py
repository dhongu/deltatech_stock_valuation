# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Teste pentru constatările din readme/bugs.md (VA-001 … VA-004).

import polib

from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tools.misc import file_path

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestValuationAreaBugs(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.area_default = cls.env["valuation.area"].create({"name": "Default", "code": "STD"})
        cls.area_wh = cls.env["valuation.area"].create({"name": "Warehouse", "code": "WH"})
        company.write({"use_valuation_area": True, "valuation_area_id": cls.area_default.id})

        # aria e pusă DOAR pe depozit, nu și pe locația lui de stoc
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        cls.warehouse.valuation_area_id = cls.area_wh
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.stock_location.valuation_area_id = False

        cls.account_stock = cls.env["account.account"].create(
            {"name": "Stock", "code": "371VA", "account_type": "asset_current"}
        )
        cls.account_loss = cls.env["account.account"].create(
            {"name": "Inventory loss", "code": "607VA", "account_type": "expense"}
        )
        cls.inventory_loc = cls.env["stock.location"].search(
            [("usage", "=", "inventory"), ("company_id", "in", [company.id, False])], limit=1
        )
        cls.inventory_loc.valuation_account_id = cls.account_loss
        categ = cls.env["product.category"].create(
            {
                "name": "Real time",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_stock.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Storable VA", "is_storable": True, "standard_price": 10.0, "categ_id": categ.id}
        )

    def _internal_location(self, name, area=False):
        return self.env["stock.location"].create(
            {
                "name": name,
                "usage": "internal",
                "location_id": self.stock_location.id,
                "valuation_area_id": area and area.id,
            }
        )

    def _done_move(self, location, location_dest, qty=1.0):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "uom_id": self.product.uom_id.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    # VA-001 ------------------------------------------------------------------------------

    def test_va001_inventory_adjustment_uses_warehouse_area(self):
        quant = self.env["stock.quant"].create(
            {"product_id": self.product.id, "location_id": self.stock_location.id, "inventory_quantity": 5}
        )
        quant.action_apply_inventory()
        move = self.env["stock.move"].search([("product_id", "=", self.product.id)])
        self.assertEqual(len(move), 1)
        self.assertFalse(move.warehouse_id, "adjustments carry no procurement warehouse")
        self.assertEqual(move._get_valuation_area(), self.area_wh)
        self.assertTrue(move.account_move_id, "the adjustment must create a stock entry")
        self.assertEqual(move.account_move_id.line_ids.valuation_area_id, self.area_wh)

    def test_va001_manual_transfer_uses_warehouse_area(self):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "uom_id": self.product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.stock_location.id,
            }
        )
        self.assertFalse(move.warehouse_id)
        self.assertEqual(move._get_valuation_area(), self.area_wh)

    def test_va001_location_area_has_priority_over_warehouse(self):
        shelf = self._internal_location("Shelf STD", self.area_default)
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "uom_id": self.product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": shelf.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        self.assertEqual(move._get_valuation_area(), self.area_default)

    # VA-003 ------------------------------------------------------------------------------

    def test_va003_internal_move_between_areas_blocked(self):
        shelf = self._internal_location("Shelf STD", self.area_default)
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 5.0)
        with self.assertRaises(UserError):
            self._done_move(self.stock_location, shelf)

    def test_va003_move_line_to_other_area_blocked(self):
        # mișcarea e în aceeași arie, dar linia merge pe o sublocație din altă arie
        shelf = self._internal_location("Shelf STD", self.area_default)
        other = self._internal_location("Other WH", self.area_wh)
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 5.0)
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "uom_id": self.product.uom_id.id,
                "location_id": self.stock_location.id,
                "location_dest_id": other.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.write({"location_dest_id": shelf.id, "quantity": 1.0, "picked": True})
        with self.assertRaises(UserError):
            move._action_done()

    def test_va003_internal_move_same_area_allowed(self):
        # sursa fără arie proprie moștenește aria depozitului; destinația are explicit aceeași arie
        shelf = self._internal_location("Shelf WH", self.area_wh)
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 5.0)
        move = self._done_move(self.stock_location, shelf)
        self.assertEqual(move.state, "done")
        self.assertEqual(move._get_valuation_area(), self.area_wh)

    def test_va003_check_ignored_without_valuation_area(self):
        self.env.company.use_valuation_area = False
        shelf = self._internal_location("Shelf STD", self.area_default)
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 5.0)
        self.assertEqual(self._done_move(self.stock_location, shelf).state, "done")

    # VA-002 ------------------------------------------------------------------------------

    def test_va002_manual_entry_with_product_quantity_area(self):
        with Form(self.env["account.move"].with_context(default_move_type="entry")) as move_form:
            with move_form.line_ids.new() as line:
                line.account_id = self.account_stock
                line.product_id = self.product
                line.quantity = 3.0
                line.valuation_area_id = self.area_wh
                line.debit = 30.0
            with move_form.line_ids.new() as line:
                line.account_id = self.account_loss
                line.credit = 30.0
        move = move_form.record
        stock_line = move.line_ids.filtered(lambda aml: aml.account_id == self.account_stock)
        self.assertRecordValues(
            stock_line,
            [
                {
                    "product_id": self.product.id,
                    "quantity": 3.0,
                    "product_uom_id": self.product.uom_id.id,
                    "valuation_area_id": self.area_wh.id,
                }
            ],
        )

    def test_va002_journal_items_list_has_quantity_and_area(self):
        arch = self.env["account.move.line"].get_view(self.env.ref("account.view_move_line_tree").id, "list")["arch"]
        self.assertIn('name="quantity"', arch)
        self.assertIn('name="valuation_area_id"', arch)

    # VA-004 ------------------------------------------------------------------------------

    def test_va004_area_form_has_sheet(self):
        arch = self.env["valuation.area"].get_view(
            self.env.ref("deltatech_valuation_area.view_valuation_area_form").id
        )["arch"]
        self.assertIn("<sheet", arch)

    def test_va004_stock_journal_restricted(self):
        field = self.env["valuation.area"]._fields["stock_journal_id"]
        self.assertTrue(field.check_company)
        self.assertIn(("type", "=", "general"), field.domain)

    def test_va004_code_help_not_misleading(self):
        self.assertNotIn("account determination", self.env["valuation.area"]._fields["code"].help)

    def test_va004_menu_restricted_to_area_writers(self):
        menu = self.env.ref("deltatech_valuation_area.menu_valuation_area")
        self.assertIn(self.env.ref("account.group_account_manager"), menu.group_ids)

    def test_va004_romanian_terminology(self):
        po = polib.pofile(file_path("deltatech_valuation_area/i18n/ro.po"))
        mixed = [entry.msgid for entry in po if "zon" in entry.msgstr.lower()]
        self.assertFalse(mixed, "ro.po must use 'arie de evaluare' only")
