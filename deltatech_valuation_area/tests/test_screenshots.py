# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_valuation_area`,
# generate în timpul testelor, în limba RO, pe planul de conturi RO (setup_country("ro")).
#
# Seed determinist: companie RO cu Use Valuation Area activ și o arie implicită
# ([STD] Arie standard, pe jurnalul de stoc al companiei), o a doua arie ([DEP] Arie
# depozit, cu jurnal de stoc propriu) atașată depozitului „Depozit central" și locației
# lui de stoc, o locație internă separată („Raft magazin") cu aria [STD], o notă de stoc
# generată automat la un plus de inventar (Dr 371 / Cr 607, aria [DEP]) și o factură de
# furnizor cu produs stocabil (Dr 371 + 4426 / Cr 401, aria [STD] pe linia produsului).
#
# Prima captură arată și setarea „Păstrează valoarea mișcării la recalcularea retroactivă"
# (`valuation_keep_move_value`, doar în Odoo 20), din același bloc „Evaluare" al Setărilor.
#
# Rulare:
#   .venv/bin/python odoo/odoo-bin -c odoo.conf -d test20 -i l10n_ro,deltatech_valuation_area,l10n_ro_doc_screenshots \
#       --without-demo=all --test-tags=fise_screenshots --stop-after-init --http-port=8170
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

        # „Locații de stocare" activă: meniul Locații (pașii 5 și 6) cere acest grup, iar bifa
        # apare activă în captura Setărilor
        env.ref("base.group_user").write({"implied_ids": [(4, env.ref("stock.group_stock_multi_locations").id)]})

        # jurnalul de stoc al companiei (cel standard, din Setări Contabilitate) pentru aria
        # implicită și un jurnal de stoc propriu pentru aria depozitului — ilustrează câmpul
        # „Jurnal de stoc" al ariei (folosit de deltatech_obyc la notele de stoc)
        cls.stock_journal = company.account_stock_journal_id or env["account.journal"].create(
            {"name": "Evaluare stoc", "type": "general", "code": "STK", "company_id": company.id}
        )
        cls.stock_journal_dep = env["account.journal"].create(
            {"name": "Stoc depozit", "type": "general", "code": "STKD", "company_id": company.id}
        )

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
                "stock_journal_id": cls.stock_journal_dep.id,
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

        cls.supplier = cls.partner_a
        cls.supplier.name = "Furnizor Demo SRL"

        # depozit + locație internă cu arii proprii
        cls.warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if cls.warehouse:
            # nume lizibile în capturi (fixture-ul de test creează „company_1_data")
            cls.warehouse.write({"name": "Depozit central", "code": "DC", "valuation_area_id": cls.area_warehouse.id})
            cls.location = cls.warehouse.lot_stock_id
            # aria depozitului se pune și pe locația lui de stoc: mișcările fără depozit
            # (ajustări de inventar, transferuri manuale) iau aria din locație
            cls.location.write({"name": "Stoc", "valuation_area_id": cls.area_warehouse.id})
        else:
            cls.location = env["stock.location"].search(
                [("usage", "=", "internal"), ("company_id", "=", company.id)], limit=1
            )
        # o locație internă separată, cu arie proprie (prioritate maximă la determinare)
        cls.location_area = env["stock.location"].create(
            {
                "name": "Raft magazin",
                "usage": "internal",
                "location_id": (cls.warehouse.view_location_id or cls.location.location_id).id,
                "company_id": company.id,
                "valuation_area_id": cls.area_default.id,
            }
        )

        # notă de stoc generată AUTOMAT: plus la inventar pe DC/Stoc, produs cu evaluare
        # în timp real; locația de ajustare are contul de pierderi 607 (Cheltuieli privind
        # mărfurile) => Dr 371 / Cr 607, cu aria [DEP] și cantitatea +5 pe debit
        cls.account_607 = env["account.account"].search(
            [("code", "=like", "607%"), ("company_ids", "in", [company.id])], order="code", limit=1
        )
        cls.inventory_loc = env["stock.location"].search(
            [("usage", "=", "inventory"), ("company_id", "in", [company.id, False])], limit=1
        )
        cls.auto_move = env["account.move"]
        cls.auto_stock_line = env["account.move.line"]
        cls.bill = env["account.move"]
        cls.invoice = env["account.move"]
        if cls.account_607 and cls.inventory_loc and cls.warehouse:
            cls.inventory_loc.valuation_account_id = cls.account_607.id
            categ = env["product.category"].create(
                {
                    "name": "Mărfuri (evaluare în timp real)",
                    "property_valuation": "real_time",
                    "property_cost_method": "average",
                    "property_stock_valuation_account_id": cls.account_stock.id,
                }
            )
            cls.product_rt = env["product.product"].create(
                {"name": "Marfă inventariată", "is_storable": True, "standard_price": 20.0, "categ_id": categ.id}
            )
            quant = env["stock.quant"].create(
                {"product_id": cls.product_rt.id, "location_id": cls.location.id, "inventory_quantity": 5}
            )
            quant.with_context(inventory_name="Plus la inventar").action_apply_inventory()
            stock_move = env["stock.move"].search([("product_id", "=", cls.product_rt.id)], limit=1)
            cls.auto_move = stock_move.account_move_id
            # linia 371 a notei automate (cantitatea semnată +5 se vede în formularul liniei)
            cls.auto_stock_line = cls.auto_move.line_ids.filtered(lambda line: line.debit > 0)[:1]

            # recepție manuală (fără comandă de achiziție) a 10 buc × 20 lei pe DC/Raft magazin ([STD]);
            # cu evaluarea perpetuă la facturare recepția nu generează notă — marfa intră în 371
            # prin factura de furnizor de mai jos, care primește aria implicită [STD]
            supplier_loc = env.ref("stock.stock_location_suppliers")
            receipt_type = cls.warehouse.in_type_id
            cls.receipt = env["stock.picking"].create(
                {
                    "picking_type_id": receipt_type.id,
                    "partner_id": cls.supplier.id,
                    "location_id": supplier_loc.id,
                    "location_dest_id": cls.location_area.id,
                    "move_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": cls.product_rt.id,
                                "product_uom_qty": 10,
                                "uom_id": cls.product_rt.uom_id.id,
                                "location_id": supplier_loc.id,
                                "location_dest_id": cls.location_area.id,
                            },
                        )
                    ],
                }
            )
            cls.receipt.action_confirm()
            cls.receipt.move_ids.write({"quantity": 10, "picked": True})
            cls.receipt.button_validate()

            # factură de furnizor pentru marfa recepționată (evaluare perpetuă la facturare):
            # aria se completează pe linia produsului din aria implicită a companiei
            cls.bill = env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": cls.supplier.id,
                    "invoice_date": fields.Date.today(),
                    "ref": "FF-1001",
                    "invoice_line_ids": [(0, 0, {"product_id": cls.product_rt.id, "quantity": 10, "price_unit": 20.0})],
                }
            )
            cls.bill.action_post()

            # livrare manuală a 3 buc din DC/Raft magazin (fără notă: locația client nu are cont)
            customer_loc = env.ref("stock.stock_location_customers")
            cls.customer = env["res.partner"].create({"name": "Client Demo SRL"})
            cls.delivery = env["stock.picking"].create(
                {
                    "picking_type_id": cls.warehouse.out_type_id.id,
                    "partner_id": cls.customer.id,
                    "location_id": cls.location_area.id,
                    "location_dest_id": customer_loc.id,
                    "move_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": cls.product_rt.id,
                                "product_uom_qty": 3,
                                "uom_id": cls.product_rt.uom_id.id,
                                "location_id": cls.location_area.id,
                                "location_dest_id": customer_loc.id,
                            },
                        )
                    ],
                }
            )
            cls.delivery.action_confirm()
            cls.delivery.action_assign()
            cls.delivery.move_ids.write({"quantity": 3, "picked": True})
            cls.delivery.button_validate()

            # factură de client: Odoo 20 adaugă liniile de descărcare (Dr 607 / Cr 371, la cost),
            # cu aria implicită și cantitatea facturată pozitivă pe ambele linii
            cls.categ_rt = categ
            categ.property_account_expense_categ_id = cls.account_607.id
            cls.invoice = env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": cls.customer.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [(0, 0, {"product_id": cls.product_rt.id, "quantity": 3, "price_unit": 150.0})],
                }
            )
            cls.invoice.action_post()

        cls.act_settings = env.ref("stock.action_stock_config_settings").id
        cls.act_area = env.ref("deltatech_valuation_area.action_valuation_area").id
        cls.act_warehouse = env.ref("stock.action_warehouse_form").id

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
                // spațiu la stânga valorilor, ca bulina numerotată să nu acopere prima cifră/literă
                const padded = ["code", "stock_journal_id", "valuation_area_id", "quantity", "product_id"]
                    .map((n) => `.o_form_view .o_wrap_input div[name='${n}']`).join(", ");
                document.querySelectorAll(padded).forEach((e) => {
                    e.style.paddingLeft = "16px";
                });
            }
        """
        # JS: afișează coloana opțională „Valuation Area" din lista liniilor notei contabile,
        # apoi dă click pe tab-ul „Journal Items" ca să rămână vizibilă în captură.
        show_optional_area_col_js = """
            async () => {
                // coloana opțională de afișat: aria de evaluare (lista liniilor unei note
                // contabile din Odoo 20 nu are coloană de cantitate)
                const groups = [["Valuation Area", "Arie de evaluare", "Arie evaluare"]];
                for (const labels of groups) {
                    const tg = document.querySelector(
                        "table .o_optional_columns_dropdown_toggle, .o_list_table .dropdown-toggle.o_optional_columns_dropdown_toggle"
                    );
                    if (!tg) { break; }
                    if (!document.querySelector(".o-dropdown--menu .dropdown-item, .dropdown-menu .dropdown-item")) {
                        tg.click();
                        await new Promise((r) => setTimeout(r, 600));
                    }
                    const item = [...document.querySelectorAll(".dropdown-menu .dropdown-item, .o-dropdown--menu .dropdown-item")]
                        .find((e) => labels.some((t) => e.textContent.trim() === t));
                    if (item) {
                        const cb = item.querySelector("input[type=checkbox]");
                        if (!cb || !cb.checked) { (cb || item).click(); }
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
                // ascunde butonul „Nou(ă)" din control panel (consultăm documente existente)
                const btnNew = [...document.querySelectorAll(".o_control_panel button")].find(
                    (e) => ["Nou(ă)", "New"].includes(e.textContent.trim())
                );
                if (btnNew) { btnNew.style.display = "none"; }
            }
        """

        shots = [
            # 1. Setări Inventar — secțiunea Valuation: Use Valuation Area + aria implicită
            #    și setarea „Păstrează valoarea mișcării la recalcularea retroactivă"
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "01_setari_use_valuation_area.png",
                "wait": ".o_form_view",
                "eval": scroll_to_valuation_js,
                "eval_wait": 800,
                "highlight": ["#valuation_area", "#valuation_keep_move_value"],
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
            #    Folosim lista, mai compactă; pe bazele cu stock_barcode, formularul de
            #    depozit randează un barcode care crapă în mediul de test (rlPyCairo lipsă).
            {
                "path": f"/web?debug=0#action={self.act_warehouse}&view_type=list",
                "name": "04_depozit_valuation_area.png",
                "wait": ".o_list_view",
                "highlight": ["td[name='valuation_area_id']"],
                "settle": 2000,
            },
            # 5. Formularul unei locații interne cu câmpul „Arie de evaluare" (tab-ul
            #    informațiilor suplimentare). Fără stock_barcode instalat, formularul se încarcă.
            {
                "path": f"/web?debug=0#id={self.location_area.id}&model=stock.location&view_type=form",
                "name": "05_locatie_valuation_area.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": ["div[name='valuation_area_id']"],
                "settle": 2000,
            },
        ]
        if self.auto_move:
            # 6. Nota de stoc generată automat la ajustarea de inventar: aria pe ambele linii
            shots.append(
                {
                    "path": f"/web?debug=0#id={self.auto_move.id}&model=account.move&view_type=form",
                    "name": "06_nota_stoc_automata.png",
                    "wait": ".o_form_view",
                    "click_tab": "Journal Items",
                    "eval": show_optional_area_col_js,
                    "eval_wait": 1200,
                    "settle": 2500,
                }
            )
        if self.auto_stock_line:
            # 7. Formularul liniei 371 din nota automată: cantitatea semnată (+5) și produsul
            shots.append(
                {
                    "path": f"/web?debug=0#id={self.auto_stock_line.id}&model=account.move.line&view_type=form",
                    "name": "07_linie_stoc_cantitate.png",
                    "wait": ".o_form_view",
                    "eval": hide_new_btn_js,
                    "highlight": ["div[name='quantity']", "div[name='product_id']"],
                    "settle": 2500,
                }
            )
        if self.bill:
            # 8. Factura de furnizor: tab-ul Elemente jurnal, aria pe linia produsului
            shots.append(
                {
                    "path": f"/web?debug=0#id={self.bill.id}&model=account.move&view_type=form",
                    "name": "08_factura_furnizor_valuation_area.png",
                    "wait": ".o_form_view",
                    "click_tab": "Journal Items",
                    "eval": show_optional_area_col_js,
                    "eval_wait": 1200,
                    "settle": 2500,
                }
            )
        if self.invoice:
            # 9. Factura de client: liniile de descărcare (607 / 371) cu aria și cantitatea +3
            shots.append(
                {
                    "path": f"/web?debug=0#id={self.invoice.id}&model=account.move&view_type=form",
                    "name": "09_factura_client_descarcare.png",
                    "wait": ".o_form_view",
                    "click_tab": "Journal Items",
                    "eval": show_optional_area_col_js,
                    "eval_wait": 1200,
                    "settle": 2500,
                }
            )
        self.capture_screenshots(shots)
