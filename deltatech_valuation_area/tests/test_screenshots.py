# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_valuation_area`,
# generate în timpul testelor, în limba RO, pe planul de conturi RO (setup_country("ro")).
#
# Seed determinist: companie RO cu Use Valuation Area activ și o arie implicită
# ([STD] Arie standard), un jurnal de stoc, o a doua arie ([DEP] Arie depozit) atașată
# depozitului principal, câmpul `valuation_area_id` setat pe o locație internă și o notă
# de stoc postată pe contul 371 cu aria de evaluare completată pe linia produsului.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -u deltatech_valuation_area \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.l10n_ro_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestValuationAreaScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_valuation_area"

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ro")
    def setUpClass(cls):
        if ScreenshotCase is None:
            raise unittest.SkipTest("l10n_ro_doc_screenshots indisponibil")
        super().setUpClass()
        cls.prepare_ro_company(name="RO Company")  # RON, drepturi contabile, limba RO, light theme
        company = cls.env.company
        cls.env.ref("base.user_admin").write({"company_ids": [(4, company.id)], "company_id": company.id})

        env = cls.env

        # jurnalul de stoc (asociat ariei de evaluare)
        cls.stock_journal = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)], limit=1
        ) or env["account.journal"].create({"name": "Stoc", "type": "general", "code": "STK", "company_id": company.id})

        # aria implicită pe companie + o a doua arie pentru depozit
        cls.area_default = env["valuation.area"].create(
            {
                "code": "STD",
                "name": "Arie standard",
                "company_id": company.id,
                "stock_journal_id": cls.stock_journal.id,
            }
        )
        cls.area_warehouse = env["valuation.area"].create(
            {
                "code": "DEP",
                "name": "Arie depozit",
                "company_id": company.id,
                "stock_journal_id": cls.stock_journal.id,
            }
        )

        # activează aria de evaluare pe companie + fallback
        company.use_valuation_area = True
        company.valuation_area_id = cls.area_default.id

        # contul de stoc 371 (Mărfuri) din planul RO
        cls.account_stock = env["account.account"].search(
            [("code", "=like", "371%"), ("company_ids", "in", [company.id])], order="code", limit=1
        )
        if not cls.account_stock:
            cls.account_stock = env["account.account"].create(
                {"name": "Mărfuri", "code": "371000", "account_type": "asset_current"}
            )

        cls.counterpart_account = cls.company_data["default_account_expense"]

        # depozit + locație internă cu arii proprii
        cls.warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if cls.warehouse:
            cls.warehouse.valuation_area_id = cls.area_warehouse.id
            cls.location = cls.warehouse.lot_stock_id
            cls.location.valuation_area_id = cls.area_warehouse.id
        else:
            cls.location = env["stock.location"].search(
                [("usage", "=", "internal"), ("company_id", "=", company.id)], limit=1
            )
            if cls.location:
                cls.location.valuation_area_id = cls.area_warehouse.id

        cls.product = cls.product_a
        cls.product.write({"name": "Marfă demo", "is_storable": True})

        # nota de stoc CU produs — debit 371 1000, cantitate +10, aria completată pe linie
        cls.move_in = cls._post_stock_entry("Recepție mărfuri în magazin", 1000.0, quantity=10.0)

        cls.act_settings = env.ref("stock.action_stock_config_settings").id
        cls.act_area = env.ref("deltatech_valuation_area.action_valuation_area").id
        cls.act_warehouse = env.ref("stock.action_warehouse_form").id

    @classmethod
    def _post_stock_entry(cls, label, debit, quantity=10.0):
        """Notă de stoc tip `entry`: debit 371 qty=+quantity (intrare), credit cheltuială."""
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": cls.stock_journal.id,
                "date": fields.Date.today(),
                "ref": label,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "account_id": cls.account_stock.id,
                            "product_id": cls.product.id,
                            "product_uom_id": cls.product.uom_id.id,
                            "quantity": quantity,  # +10 pe debit (intrare)
                            "debit": debit,
                            "credit": 0.0,
                            "valuation_area_id": cls.area_default.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Contrapartidă cheltuială",
                            "account_id": cls.counterpart_account.id,
                            "debit": 0.0,
                            "credit": debit,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def test_capture_fise(self):
        # JS: derulează pagina de setări până la secțiunea Valuation (containerul nostru setting)
        scroll_to_valuation_js = """
            () => {
                const el = document.querySelector("#valuation_area")
                    || [...document.querySelectorAll(".o_setting_box, .o_settings_container .o_form_label")]
                        .find((e) => /valuation area|arie de evaluare/i.test(e.textContent));
                if (el) { el.scrollIntoView({block: 'center'}); }
            }
        """
        # JS: ascunde butonul „Nou(ă)" din control panel (consultăm înregistrări existente)
        hide_new_btn_js = """
            () => {
                document.querySelectorAll(
                    ".o_control_panel .o_form_button_create, .o_control_panel .o-form-buttonbox-new"
                ).forEach((e) => { e.style.display = "none"; });
                const btn = [...document.querySelectorAll(".o_control_panel button")].find(
                    (e) => ["Nou(ă)", "New"].includes(e.textContent.trim())
                );
                if (btn) { btn.style.display = "none"; }
            }
        """
        # JS: afișează coloana opțională „Valuation Area" din lista liniilor notei contabile,
        # apoi dă click pe tab-ul „Journal Items" ca să rămână vizibilă în captură.
        show_optional_area_col_js = """
            async () => {
                const toggle = document.querySelector(
                    "table .o_optional_columns_dropdown_toggle, .o_list_table .dropdown-toggle.o_optional_columns_dropdown_toggle"
                );
                if (toggle) {
                    toggle.click();
                    await new Promise((r) => setTimeout(r, 600));
                    const labels = ["Valuation Area", "Arie de evaluare", "Arie evaluare"];
                    const item = [...document.querySelectorAll(".dropdown-menu .dropdown-item, .o-dropdown--menu .dropdown-item")]
                        .find((e) => labels.some((t) => e.textContent.includes(t)));
                    if (item) {
                        const cb = item.querySelector("input[type=checkbox]");
                        if (!cb || !cb.checked) { item.click(); }
                    }
                    await new Promise((r) => setTimeout(r, 600));
                }
                // închide dropdown-ul de coloane opționale (OWL) cu Escape, ca să nu
                // acopere valoarea ariei pe linia produsului
                document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
                await new Promise((r) => setTimeout(r, 400));
                // un click pe fundalul gol al formularului (nu pe breadcrumb) închide orice
                // dropdown OWL rămas deschis, fără să navigheze
                document.querySelector(".o_form_sheet_bg, .o_content")?.click();
                await new Promise((r) => setTimeout(r, 600));
            }
        """

        shots = [
            # 1. Setări Inventar — secțiunea Valuation: Use Valuation Area + aria implicită
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "01_setari_use_valuation_area.png",
                "wait": ".o_form_view",
                "eval": scroll_to_valuation_js,
                "eval_wait": 800,
                "highlight": ["#valuation_area"],
                "settle": 2500,
            },
            # 2. Lista ariilor de evaluare (cod / nume / companie / jurnal de stoc)
            {
                "path": f"/web?debug=0#action={self.act_area}&view_type=list",
                "name": "02_valuation_area_list.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 3. Formularul unei arii de evaluare cu code, company și stock journal
            {
                "path": f"/web?debug=0#id={self.area_default.id}&model=valuation.area&view_type=form",
                "name": "03_valuation_area_form.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": [
                    "field[name='code'], div[name='code']",
                    "field[name='stock_journal_id'], div[name='stock_journal_id']",
                ],
                "settle": 2000,
            },
            # 4. Lista depozitelor cu coloana Valuation Area (depozitul are arie proprie).
            #    Folosim lista, nu formularul de depozit/locație: formularul randează un
            #    barcode (stock_barcode) care crapă în mediul de test (rlPyCairo lipsă) și
            #    blochează încărcarea paginii.
            {
                "path": f"/web?debug=0#action={self.act_warehouse}&view_type=list",
                "name": "04_depozit_valuation_area.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 6. Linia contabilă de stoc cu coloana Valuation Area afișată
            {
                "path": f"/web?debug=0#id={self.move_in.id}&model=account.move&view_type=form",
                "name": "05_linie_contabila_valuation_area.png",
                "wait": ".o_form_view",
                "click_tab": "Journal Items",
                "eval": show_optional_area_col_js,
                "eval_wait": 1200,
                "settle": 2500,
            },
        ]
        self.capture_screenshots(shots)
