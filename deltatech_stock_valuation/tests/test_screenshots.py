# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_stock_valuation`,
# generate în timpul testelor, în limba RO, pe planul de conturi RO (setup_country("ro")).
#
# Seed determinist: companie RO cu aria de evaluare la nivel de companie, un cont 371 marcat
# Stock Valuation, o categorie de produs cu Use Valuation Area Price (AVCO), o notă de stoc
# postată cu cantitate semnată (+10 pe debit / -10 pe credit) și câteva rânduri în
# product.valuation / product.valuation.history.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -u deltatech_stock_valuation \
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

        cls.counterpart_account = cls.company_data["default_account_expense"]
        cls.journal = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)], limit=1
        ) or env["account.journal"].create({"name": "Diverse", "type": "general", "code": "DIV"})

        # categorie de produs AVCO cu Use Valuation Area Price activ (+ cont de stoc 371)
        cls.categ = env["product.category"].create(
            {
                "name": "Mărfuri evaluare arie",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_stock.id,
                "use_valuation_area_price": True,
            }
        )

        cls.product = cls.product_a
        cls.product.write({"name": "Marfă demo", "is_storable": True, "categ_id": cls.categ.id})

        # nota de stoc CU produs — debit 1000, cantitate +10 (convenția semnată: qty pozitiv pe debit)
        cls.move_in = cls._post_stock_entry(
            "Recepție mărfuri în magazin", 1000.0, quantity=10.0
        )

        # seed product.valuation + product.valuation.history (sold curent + istoric lunar)
        month = fields.Date.today().strftime("%Y%m")
        common = {
            "product_id": cls.product.id,
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "valuation_area_id": cls.valuation_area.id if cls.valuation_area else False,
            "account_id": cls.account_stock.id,
            "company_id": company.id,
            "currency_id": company.currency_id.id,
        }
        pv_domain = [
            ("product_id", "=", cls.product.id),
            ("account_id", "=", cls.account_stock.id),
            ("company_id", "=", company.id),
        ]
        if cls.valuation_area:
            pv_domain.append(("valuation_area_id", "=", cls.valuation_area.id))
        pv = env["product.valuation"].search(pv_domain, limit=1)
        pv_vals = {"price": 100.0, "quantity": 10.0, "amount": 1000.0}
        if pv:
            pv.write(pv_vals)
        else:
            env["product.valuation"].create(dict(common, **pv_vals))

        pvh_domain = pv_domain + [("month", "=", month)]
        pvh = env["product.valuation.history"].search(pvh_domain, limit=1)
        pvh_vals = {
            "quantity_initial": 0.0,
            "amount_initial": 0.0,
            "quantity_in": 10.0,
            "debit": 1000.0,
            "quantity_out": 0.0,
            "credit": 0.0,
        }
        if pvh:
            pvh.write(pvh_vals)
        else:
            env["product.valuation.history"].create(dict(common, month=month, **pvh_vals))

        cls.act_settings = env.ref("stock.action_stock_config_settings").id
        cls.act_pv = env.ref("deltatech_stock_valuation.product_valuation_action").id
        cls.act_pvh = env.ref("deltatech_stock_valuation.product_valuation_history_action").id

    @classmethod
    def _post_stock_entry(cls, label, debit, quantity=10.0):
        """Notă de stoc tip `entry`: debit 371 qty=+quantity, credit cheltuială qty=-quantity."""
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": cls.journal.id,
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
                            "valuation_area_id": cls.valuation_area.id if cls.valuation_area else False,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Contrapartidă cheltuială",
                            "account_id": cls.counterpart_account.id,
                            "product_id": cls.product.id,
                            "product_uom_id": cls.product.uom_id.id,
                            "quantity": -quantity,  # -10 pe credit (ieșire), convenția semnată
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
        # JS: derulează pagina de setări până la secțiunea Valuation (containerul nostru)
        scroll_to_valuation_js = """
            () => {
                const el = document.querySelector(
                    "#compute_deltatech_stock_valuation, #module_deltatech_stock_valuation"
                );
                if (el) { el.scrollIntoView({block: 'start'}); }
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
            # 2. Categoria de produs cu Use Valuation Area Price bifat
            {
                "path": f"/web?debug=0#id={self.categ.id}&model=product.category&view_type=form",
                "name": "02_categorie_use_area_price.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": ["div[name='use_valuation_area_price']"],
                "settle": 2000,
            },
            # 3. Setări Inventar — secțiunea Valuation (Use Valuation Area, nivel Company,
            #    butoanele Recompute All / Start Auto Refresh)
            {
                "path": f"/web?debug=0#action={self.act_settings}",
                "name": "03_setari_refresh.png",
                "wait": "#compute_deltatech_stock_valuation, #module_deltatech_stock_valuation",
                "eval": scroll_to_valuation_js,
                "highlight": [
                    "field[name='valuation_area_level'], div[name='valuation_area_level']",
                    "button[name='action_recompute_in_background']",
                ],
                "settle": 2500,
            },
            # 5. Nota de stoc postată cu cantitate semnată (Journal Items: +10 debit / -10 credit)
            self.account_move_shot(self.move_in, "05_nota_cantitate_semnata.png"),
            # 6. Lista product.valuation (produs / arie / cont / valoare)
            {
                "path": f"/web?debug=0#action={self.act_pv}&view_type=list",
                "name": "06_product_valuation_list.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 7. Lista product.valuation.history (luna / valoare)
            {
                "path": f"/web?debug=0#action={self.act_pvh}&view_type=list",
                "name": "07_valuation_history.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 8. Template-ul produsului cu tabelul Product Valuations (tab Accounting / Invoicing)
            {
                "path": f"/web?debug=0#id={self.product.product_tmpl_id.id}"
                f"&model=product.template&view_type=form",
                "name": "08_template_valuations.png",
                "wait": ".o_form_view",
                "click_tab": "Contabilitate",
                "eval": hide_new_btn_js,
                "highlight": ["field[name='product_valuation_ids'], div[name='product_valuation_ids']"],
                "settle": 2500,
            },
        ]
        self.capture_screenshots(shots)
