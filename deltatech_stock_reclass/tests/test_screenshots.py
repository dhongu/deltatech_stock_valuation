# ©  2026 Terrabit
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant (RO) și pentru readme/USAGE.md (EN) ale modulului
# `deltatech_stock_reclass`, generate în timpul testelor, pe planul de conturi RO.
#
# Seed determinist: compania „RO Company", produsul „Marfă de reclasificat" (cost 25 RON, 10 buc.
# în Depozit central), regula 3028 → 371 cu decizia conducerii obligatorie și patru documente:
# unul validat (nota Dr 371 / Cr 3028), unul validat și apoi anulat, unul în ciornă, gata de
# validare, și unul în ciornă fără decizia conducerii, refuzat la validare.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -i l10n_ro,deltatech_stock_reclass,deltatech_doc_screenshots \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.deltatech_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestStockReclassificationScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_stock_reclass"

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

        Account = env["account.account"]
        cls.acc_3028 = Account.search(
            [("code", "=like", "3028%"), ("company_ids", "in", company.id)], order="code", limit=1
        )
        cls.acc_371 = Account.search(
            [("code", "=like", "371%"), ("company_ids", "in", company.id)], order="code", limit=1
        )
        # jurnalul propus implicit pe document: cel de stoc al companiei
        cls.journal = company.account_stock_journal_id or env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "general")], limit=1
        )

        cls.warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        # nume lizibile în capturi (fixture-ul de test creează „company_1_data")
        cls.warehouse.write({"name": "Depozit central", "code": "DC"})
        cls.warehouse.in_type_id.name = "Recepții"
        cls.stock = cls.warehouse.lot_stock_id
        cls.supplier = cls.partner_a
        cls.supplier.name = "Furnizor Demo SRL"

        cls.product = env["product.product"].create(
            {"name": "Marfă de reclasificat", "is_storable": True, "standard_price": 25.0}
        )
        picking_type = cls.warehouse.in_type_id
        receipt = env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": cls.supplier.id,
                "origin": "Stoc inițial",
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 10.0,
                            "product_uom": cls.product.uom_id.id,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                        }
                    )
                ],
            }
        )
        receipt.action_confirm()
        receipt.move_ids.write({"quantity": 10.0, "picked": True})
        receipt.button_validate()

        cls.rule = (
            env["stock.reclassification.rule"]
            .sudo()
            .create(
                {
                    "account_src_id": cls.acc_3028.id,
                    "account_dest_id": cls.acc_371.id,
                    "require_decision": True,
                }
            )
        )
        # numerele documentelor din capturi pornesc de la 0001, indiferent de rulările anterioare
        env["ir.sequence"].sudo().search([("code", "=", "stock.reclassification")]).number_next = 1
        cls.doc_validated = cls._document(4.0, decision="Decizia administratorului nr. 12/2026")
        cls.doc_validated.action_validate()
        # documentul anulat, câte unul pe limbă: textul notei de stornare se salvează în limba anulării
        cls.doc_cancelled = cls._document(2.0, decision="Decizia administratorului nr. 13/2026")
        cls.doc_cancelled.action_validate()
        cls.doc_cancelled.with_context(lang="ro_RO").action_cancel()
        cls.doc_cancelled_en = cls._document(2.0, decision="Decision no. 13/2026")
        cls.doc_cancelled_en.action_validate()
        cls.doc_cancelled_en.with_context(lang="en_US").action_cancel()
        cls.doc_draft = cls._document(4.0, decision="Decizia administratorului nr. 14/2026")
        cls.doc_refused = cls._document(4.0)

    @classmethod
    def _document(cls, qty, decision=False):
        return (
            cls.env["stock.reclassification"]
            .sudo()
            .create(
                {
                    "rule_id": cls.rule.id,
                    "location_src_id": cls.stock.id,
                    "location_dest_id": cls.stock.id,
                    "journal_id": cls.journal.id,
                    "decision_note": decision,
                    "line_ids": [Command.create({"product_id": cls.product.id, "quantity": qty})],
                }
            )
        )

    def _shots(self, lang="ro_RO"):
        form = ".o_form_view"
        env = self.env
        menu = env.ref("stock.menu_stock_root").id
        act_doc = env.ref("deltatech_stock_reclass.action_stock_reclassification").id
        act_rule = env.ref("deltatech_stock_reclass.action_stock_reclassification_rule").id

        def doc_url(doc):
            return f"action={act_doc}&menu_id={menu}&id={doc.id}&view_type=form"

        return [
            {
                "url": f"action={act_rule}&menu_id={menu}&id={self.rule.id}&view_type=form",
                "name": "01_regula_reclasificare.png",
                "wait": form,
                "highlight": ["div[name='account_src_id']", "div[name='account_dest_id']"],
                "settle": 2000,
            },
            {
                "url": doc_url(self.doc_draft),
                "name": "02_document_ciorna.png",
                "wait": form,
                "highlight": ["div[name='rule_id']", "button[name='action_validate']"],
                "settle": 2000,
            },
            {
                "url": doc_url(self.doc_validated),
                "name": "03_document_validat.png",
                "wait": form,
                "highlight": ["div[name='picking_id']", "div[name='account_move_id']"],
                "settle": 2000,
            },
            self.account_move_shot(self.doc_validated.account_move_id, "04_nota_contabila.png"),
            {
                "url": doc_url(self.doc_refused),
                "name": "05_decizie_obligatorie.png",
                "wait": form,
                "click_btn": "button[name='action_validate']",
                "wait_after": ".o_form_view",
                "settle": 3000,
            },
            {
                "url": doc_url(self.doc_cancelled if lang == "ro_RO" else self.doc_cancelled_en),
                "name": "06_document_anulat.png",
                "wait": form,
                "highlight": ["div[name='reverse_picking_id']", "div[name='reverse_account_move_id']"],
                "settle": 2000,
            },
        ]

    def test_capture_fise(self):
        self.capture_screenshots(self._shots())

    def test_capture_usage(self):
        self.capture_screenshots(self._shots("en_US"), lang="en_US")
