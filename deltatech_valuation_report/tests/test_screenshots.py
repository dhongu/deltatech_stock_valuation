# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa „Verificare evaluare stoc vs. balanță" — generate în timpul
# testelor, în limba RO, pe planul de conturi RO (setup_country("ro")).
#
# Seed determinist: companie RO cu aria de evaluare la nivel de companie, un cont 371 marcat
# Stock Valuation și două note postate pe el — una cu produs (debit 1000, cantitate +10,
# convenția semnată) și una FĂRĂ produs (debit 70), ca raportul să arate o diferență nenulă.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -i deltatech_valuation_report,l10n_ro_doc_screenshots \
#       --test-tags=fise_screenshots --stop-after-init
import unittest

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.l10n_ro_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestValuationReportScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_valuation_report"

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

        cls.product = cls.product_a
        cls.product.write({"name": "Marfă demo", "is_storable": True})

        # nota 1: CU produs — debit 1000, cantitate +10 (convenția semnată: qty pozitiv pe debit)
        cls._post_entry("Recepție mărfuri în magazin", 1000.0, quantity=10.0, with_product=True)
        # nota 2: FĂRĂ produs — debit 70 → diferență nenulă în raport
        cls._post_entry("Notă migrare solduri (fără produs)", 70.0, with_product=False)

        cls.act_report = env.ref("deltatech_valuation_report.action_valuation_check_report").id

    @classmethod
    def _post_entry(cls, label, debit, quantity=0.0, with_product=True):
        line = {
            "name": label,
            "account_id": cls.account_stock.id,
            "debit": debit,
            "credit": 0.0,
        }
        if with_product:
            line.update(
                {
                    "product_id": cls.product.id,
                    "product_uom_id": cls.product.uom_id.id,
                    "quantity": quantity,
                }
            )
        move = cls.env["account.move"].create(
            {
                "journal_id": cls.journal.id,
                "date": fields.Date.today(),
                "ref": label,
                "line_ids": [
                    (0, 0, line),
                    (
                        0,
                        0,
                        {
                            "name": "Contrapartidă",
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
        # JS: deschide dropdown-ul caret al liniei de cont și alege „Linii fără produs"
        # (robust la ambele limbi — UI-ul e în RO după încărcarea i18n/ro.po, dar dacă
        # traducerea lipsește se caută și textul sursă EN)
        open_caret_js = """
            async () => {
                const btn = document.querySelector("td.line_name .btn_dropdown");
                if (btn) { btn.click(); }
                await new Promise((r) => setTimeout(r, 1200));
                const labels = ["Linii fără produs", "Lines without product"];
                const item = [...document.querySelectorAll(".dropdown-item")].find(
                    (e) => labels.some((t) => e.textContent.includes(t))
                );
                if (item) { item.click(); }
                await new Promise((r) => setTimeout(r, 2500));
                // ascunde panoul de previzualizare atașamente (lasă spațiu gol în captură)
                document.querySelectorAll(".o_attachment_preview").forEach((e) => {
                    e.style.display = "none";
                });
            }
        """
        # JS: ascunde butonul de creare „Nou(ă)" din control panel — fișa arată consultarea
        # unui cont existent (salvat), nu crearea unuia nou
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
        # `?debug=0` pe prima navigare curăță session.debug (web/_handle_debug) — fără
        # pictograma de developer tools și fără tooltip-urile „?" de debug în capturi
        self.capture_screenshots(
            [
                # 1. Contul 371 din Planul de conturi, cu bifa „Evaluare stoc" (cont salvat,
                #    fără butonul „Nou(ă)", fără developer mode)
                {
                    "path": f"/web?debug=0#id={self.account_stock.id}&model=account.account&view_type=form",
                    "name": "01_conturi_stoc.png",
                    "wait": ".o_form_view",
                    "eval": hide_new_btn_js,
                    "highlight": ["div[name='is_for_stock_valuation']"],
                    "settle": 2000,
                },
                # 2. Raportul de verificare, desfășurat (cele 3 coloane + diferență nenulă)
                {
                    "path": f"/web?debug=0#action={self.act_report}",
                    "name": "02_raport_verificare.png",
                    "wait": "td.line_name",
                    "unfold_report": True,
                    "settle": 2500,
                },
                # 3. Drill-down: lista liniilor fără produs (caret „Linii fără produs")
                {
                    "path": f"/web?debug=0#action={self.act_report}",
                    "name": "03_linii_fara_produs.png",
                    "wait": "td.line_name",
                    "unfold_report": True,
                    "eval": open_caret_js,
                    "eval_wait": 1500,
                    "settle": 3000,
                },
            ],
        )
