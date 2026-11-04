# ©  2026 Terrabit
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant (RO) și pentru readme/USAGE.md (EN) ale modulului
# `deltatech_stock_valuation_guard`, generate în timpul testelor, pe planul de conturi RO.
#
# Seed determinist: compania „RO Company" pe cost mediu (AVCO), evaluare perpetuă; categoria
# „Mărfuri" aliniată și categoria „Mărfuri FIFO" pe altă metodă; produsul „Marfă fără cost"
# (stocabil, cost 0); produsul „Marfă intrată la zero", recepționat cu 10 buc. la valoare zero
# înainte de activarea blocării (rămâne în stoc valorizat la zero); apoi cele două bife pornite
# și o recepție pregătită (nevalidată) a produsului fără cost, refuzată la validare.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -i l10n_ro,deltatech_stock_valuation_guard,deltatech_doc_screenshots \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.deltatech_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestValuationGuardScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_stock_valuation_guard"

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ro")
    def setUpClass(cls):
        if ScreenshotCase is None:
            raise unittest.SkipTest("deltatech_doc_screenshots indisponibil")
        super().setUpClass()
        cls.prepare_ro_company(name="RO Company")
        env = cls.env
        company = env.company
        env.ref("base.user_admin").write({"company_ids": [(4, company.id)], "company_id": company.id})
        company.write({"cost_method": "average", "inventory_valuation": "real_time"})

        cls.categ = env["product.category"].create(
            {"name": "Mărfuri", "property_cost_method": "average", "property_valuation": "real_time"}
        )
        cls.categ_fifo = env["product.category"].create(
            {"name": "Mărfuri FIFO", "property_cost_method": "fifo", "property_valuation": "real_time"}
        )
        product_vals = {"is_storable": True, "categ_id": cls.categ.id, "standard_price": 0.0}
        cls.product_no_cost = env["product.product"].create(dict(product_vals, name="Marfă fără cost"))
        cls.product_zero = env["product.product"].create(dict(product_vals, name="Marfă intrată la zero"))
        env["product.product"].create(dict(product_vals, name="Marfă cu cost", standard_price=25.0))

        cls.warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        # nume lizibile în capturi (fixture-ul de test creează „company_1_data")
        cls.warehouse.write({"name": "Depozit central", "code": "DC"})
        cls.warehouse.in_type_id.name = "Recepții"
        cls.supplier = cls.partner_a
        cls.supplier.name = "Furnizor Demo SRL"

        # stoc intrat la valoare zero, înainte de activarea blocării
        receipt = cls._receipt(cls.product_zero, 10.0, origin="Stoc inițial fără cost")
        receipt.button_validate()

        company.write({"valuation_guard_unique_method": True, "valuation_guard_zero_cost": True})
        # recepția produsului fără cost, gata de validare: validarea e refuzată
        cls.receipt_blocked = cls._receipt(cls.product_no_cost, 5.0)

        cls.act_settings = env.ref("stock.action_stock_config_settings").id
        cls.act_categories = env.ref("deltatech_stock_valuation_guard.action_misaligned_categories").id
        cls.act_products = env.ref("deltatech_stock_valuation_guard.action_products_without_cost").id
        cls.act_zero_stock = env.ref("deltatech_stock_valuation_guard.action_zero_valued_stock").id
        cls.act_zero_moves = env.ref("deltatech_stock_valuation_guard.action_zero_valued_moves").id

    @classmethod
    def _receipt(cls, product, qty, origin=False):
        picking_type = cls.warehouse.in_type_id
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": cls.supplier.id,
                "origin": origin,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": product.uom_id.id,
                            "origin": origin,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.write({"quantity": qty, "picked": True})
        return picking

    def _shots(self):
        scroll_to_guard_js = """
            () => {
                const el = document.querySelector("#valuation_guard_unique_method");
                if (el) { el.scrollIntoView({block: 'center'}); }
            }
        """
        return [
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "01_setari_valuation_guard.png",
                "wait": ".o_form_view",
                "timeout": 60000,
                "eval": scroll_to_guard_js,
                "eval_wait": 800,
                "highlight": ["#valuation_guard_unique_method", "#valuation_guard_zero_cost"],
                "settle": 2500,
            },
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "02_confirmare_aliniere.png",
                "wait": ".o_form_view",
                "timeout": 60000,
                "eval": scroll_to_guard_js,
                "click_btn": "button[name='action_valuation_guard_align']",
                "wait_after": ".modal-dialog",
                "settle": 1500,
            },
            {
                "url": f"action={self.act_categories}",
                "name": "03_categorii_alta_metoda.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            {
                "url": f"action={self.act_products}",
                "name": "04_produse_fara_cost.png",
                "wait": ".o_list_view, .o_kanban_view",
                "settle": 2000,
            },
            {
                "url": f"id={self.receipt_blocked.id}&model=stock.picking&view_type=form",
                "name": "05_receptie_refuzata.png",
                "wait": ".o_form_view",
                "click_btn": "button[name='button_validate']",
                "wait_after": ".modal-dialog",
                "settle": 1500,
            },
            {
                "url": f"action={self.act_zero_stock}",
                "name": "06_stoc_valorizat_zero.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            {
                "url": f"action={self.act_zero_moves}",
                "name": "07_miscari_valorizate_zero.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
        ]

    def test_capture_fise(self):
        self.capture_screenshots(self._shots())

    def test_capture_usage(self):
        self.capture_screenshots(self._shots(), lang="en_US")
