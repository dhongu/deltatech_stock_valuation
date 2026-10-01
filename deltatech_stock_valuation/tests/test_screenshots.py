# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_stock_valuation`,
# generate în timpul testelor, în limba RO, pe planul de conturi RO (setup_country("ro")).
#
# Seed determinist: companie RO cu aria de evaluare la nivel de companie, contul 371 marcat
# Stock Valuation, o categorie AVCO cu evaluare perpetuă și Use Valuation Area Price, două note
# de stoc postate cu cantitate semnată — recepție Dr 371 / Cr 408 (+10 / -10) și livrare
# Dr 607 / Cr 371 (+4 / -4). product.valuation și product.valuation.history NU se seedează:
# se calculează automat la postarea notelor, ca în producție.
#
# Rulare:
#   .venv/bin/python odoo/odoo-bin -c odoo.conf -d test20 -i deltatech_stock_valuation,l10n_ro,l10n_ro_doc_screenshots \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8091
import logging
import unittest

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.l10n_ro_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestStockValuationScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_stock_valuation"

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

        # aria de evaluare la nivel de companie (cerință deltatech_stock_valuation)
        company.use_valuation_area = True
        company.valuation_area_level = "company"
        company.set_stock_valuation_at_company_level()
        cls.valuation_area = company.valuation_area_id

        # contul de stoc 371 (Mărfuri) din planul RO, marcat pentru evaluare
        cls.account_stock = env["account.account"].search(
            [("code", "=like", "371%"), ("company_ids", "in", [company.id])], order="code", limit=1
        )
        if not cls.account_stock:
            cls.account_stock = env["account.account"].create(
                {"name": "Mărfuri", "code": "371000", "account_type": "asset_current"}
            )
        cls.account_stock.is_for_stock_valuation = True

        # contrapartide din planul RO: 408 (furnizori - facturi nesosite) la recepție,
        # 607 (cheltuieli privind mărfurile) la livrare — ca notele generate de deltatech_obyc
        cls.account_408 = cls._ro_account("408", "Furnizori - facturi nesosite", "liability_current")
        cls.account_607 = cls._ro_account("607", "Cheltuieli privind mărfurile", "expense")
        cls.journal = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)], limit=1
        ) or env["account.journal"].create({"name": "Diverse", "type": "general", "code": "DIV"})

        # categorie de produs AVCO, evaluare perpetuă, cu Use Valuation Area Price activ (+ cont de stoc 371)
        cls.categ = env["product.category"].create(
            {
                "name": "Mărfuri evaluare arie",
                "property_cost_method": "average",
                "property_valuation": "real_time",
                "property_stock_valuation_account_id": cls.account_stock.id,
                "use_valuation_area_price": True,
            }
        )

        cls.product = cls.product_a
        # conturile de venit/cheltuială se moștenesc din categorie (707 / 607); product_a din
        # AccountTestInvoicingCommon are conturi proprii (701 / 601), nepotrivite pentru o marfă
        cls.product.write(
            {
                "name": "Marfă demo",
                "is_storable": True,
                "categ_id": cls.categ.id,
                "property_account_income_id": False,
                "property_account_expense_id": False,
            }
        )

        # furnizorul de pe linia 408 (soldul 408 se analizează pe partener la închiderea lunii);
        # în Odoo 20 `is_company` e calculat (CUI), deci nu se mai trimite la creare
        cls.supplier = env["res.partner"].create({"name": "Furnizor Demo SRL"})

        # convenția cantității semnate pe notele de tip entry: pozitivă pe debit, negativă pe credit
        # recepție: Dr 371 (+10) / Cr 408 (-10), 1.000 lei
        cls.move_in = cls._post_stock_entry(
            "Recepție mărfuri", cls.account_stock, cls.account_408, 1000.0, 10.0, partner=cls.supplier
        )
        # livrare: Dr 607 (+4) / Cr 371 (-4), 400 lei
        cls.move_out = cls._post_stock_entry("Livrare mărfuri", cls.account_607, cls.account_stock, 400.0, 4.0)

        # evaluarea și istoricul se recalculează AUTOMAT la postarea notelor (nu se seedează manual)
        cls.valuation = env["product.valuation"].search(
            [("product_id", "=", cls.product.id), ("account_id", "=", cls.account_stock.id)]
        )
        _logger.info(
            "Product valuation după postare: %s",
            cls.valuation.read(["quantity", "amount", "price"]),
        )

        # listă dedicată de linii contabile, cu coloana Cantitate (lista standard nu o afișează)
        cls.aml_view = env["ir.ui.view"].create(
            {
                "name": "fise.account.move.line.quantity.list",
                "model": "account.move.line",
                "type": "list",
                "arch": """
                    <list create="0" delete="0" edit="0">
                        <field name="move_name" string="Notă contabilă"/>
                        <field name="account_id"/>
                        <field name="partner_id"/>
                        <field name="product_id"/>
                        <field name="name"/>
                        <field name="quantity" string="Cantitate"/>
                        <field name="debit" sum="Total"/>
                        <field name="credit" sum="Total"/>
                        <field name="company_currency_id" column_invisible="1"/>
                    </list>
                """,
            }
        )
        cls.act_aml = (
            env["ir.actions.act_window"]
            .create(
                {
                    "name": "Elemente jurnal",
                    "res_model": "account.move.line",
                    "view_mode": "list",
                    "view_id": cls.aml_view.id,
                    "domain": str([("move_id", "in", (cls.move_in | cls.move_out).ids)]),
                    "context": "{'create': False}",
                }
            )
            .id
        )

        cls.act_settings = env.ref("stock.action_stock_config_settings").id
        cls.act_pv = env.ref("deltatech_stock_valuation.product_valuation_action").id
        cls.act_pvh = env.ref("deltatech_stock_valuation.product_valuation_history_action").id

    @classmethod
    def _ro_account(cls, prefix, name, account_type):
        company = cls.env.company
        account = cls.env["account.account"].search(
            [("code", "=like", f"{prefix}%"), ("company_ids", "in", [company.id])], order="code", limit=1
        )
        return account or cls.env["account.account"].create(
            {"name": name, "code": f"{prefix}000", "account_type": account_type}
        )

    @classmethod
    def _post_stock_entry(cls, label, debit_account, credit_account, amount, quantity, partner=None):
        """Notă de stoc tip `entry`: linia de debit cu qty=+quantity, linia de credit cu qty=-quantity.
        Aria de evaluare e obligatorie pe orice linie cu produs stocabil (deltatech_valuation_area)."""
        area = cls.valuation_area.id if cls.valuation_area else False
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": cls.journal.id,
                "date": fields.Date.today(),
                "ref": label,
                "partner_id": partner and partner.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "account_id": debit_account.id,
                            "product_id": cls.product.id,
                            "product_uom_id": cls.product.uom_id.id,
                            "quantity": quantity,  # pozitivă pe debit
                            "debit": amount,
                            "credit": 0.0,
                            "valuation_area_id": area,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "account_id": credit_account.id,
                            "product_id": cls.product.id,
                            "product_uom_id": cls.product.uom_id.id,
                            "quantity": -quantity,  # negativă pe credit
                            "debit": 0.0,
                            "credit": amount,
                            "valuation_area_id": area,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def test_capture_fise(self):
        # capturile documentează exemplul din fișă: 10 buc / 1.000 lei intrare, 4 buc / 400 lei ieșire
        self.assertRecordValues(self.valuation, [{"quantity": 6.0, "amount": 600.0, "price": 100.0}])
        history = self.env["product.valuation.history"].search(
            [("product_id", "=", self.product.id), ("account_id", "=", self.account_stock.id)]
        )
        self.assertRecordValues(
            history,
            [
                {
                    "quantity_in": 10.0,
                    "debit": 1000.0,
                    "quantity_out": 4.0,
                    "credit": 400.0,
                    "quantity_final": 6.0,
                    "amount_final": 600.0,
                }
            ],
        )
        # JS: derulează pagina de setări până la secțiunea Valuation (containerul nostru)
        scroll_to_valuation_js = """
            () => {
                const el = document.querySelector(
                    "#compute_deltatech_stock_valuation, #module_deltatech_stock_valuation"
                );
                if (el) {
                    const block = el.closest(".o_settings_container") || el;
                    block.scrollIntoView({block: "start"});
                    let sc = block.parentElement;
                    while (sc && !(sc.scrollHeight > sc.clientHeight
                                   && /(auto|scroll)/.test(getComputedStyle(sc).overflowY))) {
                        sc = sc.parentElement;
                    }
                    if (sc) { sc.scrollTop = Math.max(0, sc.scrollTop - 90); }
                }
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

        # JS: ascunde panoul de căutare lateral (filtrele implicite ale liniilor contabile)
        hide_search_panel_js = """
            () => {
                document.querySelectorAll(".o_search_panel").forEach((e) => { e.style.display = "none"; });
            }
        """
        # JS: afișează coloanele opționale Quantity In / Debit / Quantity Out / Credit în istoric
        show_in_out_js = """
            async () => {
                const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
                const toggle = document.querySelector(".o_optional_columns_dropdown_toggle");
                if (!toggle) { return; }
                toggle.click();
                await sleep(500);
                for (const label of ["Quantity In", "Debit", "Quantity Out", "Credit"]) {
                    const items = [...document.querySelectorAll(".o-dropdown--menu .o-dropdown-item, .o-dropdown--menu .dropdown-item")];
                    const item = items.find((e) => e.textContent.trim() === label);
                    const input = item && item.querySelector("input");
                    if (input && !input.checked) { input.click(); await sleep(400); }
                }
                toggle.click();
                await sleep(400);
            }
        """

        shots = [
            # 1. Contul 371 cu bifa Stock Valuation
            {
                "path": f"/web?debug=0#id={self.account_stock.id}&model=account.account&view_type=form",
                "name": "01_cont_stock_valuation.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": ["div[name='is_for_stock_valuation']"],
                "settle": 2000,
            },
            # 2. Categoria de produs: AVCO, evaluare perpetuă, Use Valuation Area Price bifat
            {
                "path": f"/web?debug=0#id={self.categ.id}&model=product.category&view_type=form",
                "name": "02_categorie_use_area_price.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": [
                    "div[name='property_cost_method']",
                    "div[name='property_valuation']",
                    "div[name='use_valuation_area_price']",
                ],
                "settle": 2000,
            },
            # 3. Setări Inventar — secțiunea Evaluare (nivel Company, arie, Recompute All (Background))
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "03_setari_refresh.png",
                "wait": "#compute_deltatech_stock_valuation, #module_deltatech_stock_valuation",
                "eval": scroll_to_valuation_js,
                "highlight": [
                    "div[name='valuation_area_level']",
                    "div[name='valuation_keep_move_value']",
                    "button[name='action_recompute_in_background']",
                ],
                "settle": 2500,
            },
            # 4. Nota de recepție postată (Dr 371 / Cr 408)
            self.account_move_shot(self.move_in, "04_nota_receptie.png"),
            # 5. Liniile celor două note, cu cantitatea semnată (+ pe debit / - pe credit)
            {
                "path": f"/web?debug=0#action={self.act_aml}&view_type=list",
                "name": "05_nota_cantitate_semnata.png",
                "wait": ".o_list_view",
                "eval": hide_search_panel_js,
                "settle": 2000,
            },
            # 6. Lista product.valuation (produs / arie / cont / preț / cantitate / valoare)
            {
                "path": f"/web?debug=0#action={self.act_pv}&view_type=list",
                "name": "06_product_valuation_list.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 7. Lista product.valuation.history (luna / sold inițial / rulaj / sold final)
            {
                "path": f"/web?debug=0#action={self.act_pvh}&view_type=list",
                "name": "07_valuation_history.png",
                "wait": ".o_list_view",
                "eval": show_in_out_js,
                "eval_wait": 1500,
                "settle": 2000,
            },
            # 8. Template-ul produsului cu tabelul Product Valuations (tab Contabilitate)
            {
                "path": f"/web?debug=0#id={self.product.product_tmpl_id.id}&model=product.template&view_type=form",
                "name": "08_template_valuations.png",
                "wait": ".o_form_view",
                "click_tab": "Contabilitate",
                "eval": hide_new_btn_js,
                "highlight": ["div[name='product_valuation_ids']"],
                "settle": 2500,
            },
        ]
        self.capture_screenshots(shots)
