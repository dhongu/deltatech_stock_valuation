# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi pentru fișa consultant a modulului `deltatech_obyc_landed_cost`, pe planul de conturi RO.
# Seed: companie RO cu arie de evaluare, regulile OBYC `stock_receipt` și `landed_cost`, o recepție
# de 10 buc. și două costuri de achiziție de 50 lei cu contul liniei 624: unul cu metoda standard
# (Dr 371 / Cr 624) și unul cu metoda „Prin cont intermediar" (Dr 371 / Cr 473900 + Dr 473900 / Cr 624000).
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -i deltatech_obyc_landed_cost \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.l10n_ro_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestLandedCostScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_obyc_landed_cost"

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ro")
    def setUpClass(cls):
        if ScreenshotCase is None:
            raise unittest.SkipTest("l10n_ro_doc_screenshots indisponibil")
        super().setUpClass()
        cls.prepare_ro_company(name="RO Company")
        company = cls.env.company
        cls.env.ref("base.user_admin").write({"company_ids": [(4, company.id)], "company_id": company.id})
        env = cls.env

        cls.account_valuation = cls._ro_account("371%", "Mărfuri", "371000", "asset_current")
        cls.account_src = cls._ro_account("408%", "Furnizori - facturi nesosite", "408000", "liability_current")
        cls.account_transport = cls._ro_account("624%", "Cheltuieli cu transportul", "624000", "expense")
        cls.account_inter = env["account.account"].create(
            {"name": "Costuri de repartizat (analitic tehnic)", "code": "473900", "account_type": "asset_current"}
        )
        cls.valuation_class = env["product.valuation.class"].create({"name": "Marfă", "code": "MF"})
        cls.stock_journal = env["account.journal"].create(
            {"name": "Stoc - Magazin central", "code": "STMC", "type": "general", "company_id": company.id}
        )
        cls.valuation_area = env["valuation.area"].create(
            {
                "name": "Magazin central",
                "code": "MAG",
                "company_id": company.id,
                "stock_journal_id": cls.stock_journal.id,
            }
        )
        company.write({"use_valuation_area": True, "valuation_area_id": cls.valuation_area.id})
        for key, src in [("stock_receipt", cls.account_src), ("landed_cost", False)]:
            env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": company.id,
                    "acc_src_id": src and src.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )
        categ = env["product.category"].create(
            {
                "name": "Mărfuri OBYC",
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product = cls.product_a
        cls.product.write(
            {
                "name": "Marfă demo OBYC",
                "is_storable": True,
                "categ_id": categ.id,
                "valuation_class_id": cls.valuation_class.id,
            }
        )
        cls.product.standard_price = 100.0
        cls.cost_product = env["product.product"].create(
            {"name": "Transport marfă", "type": "service", "landed_cost_ok": True}
        )
        warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        warehouse.code = "MAG"
        payable = env["account.account"].create(
            {"name": "Furnizori", "code": "401900", "account_type": "liability_payable", "reconcile": True}
        )
        cls.vendor = env["res.partner"].create({"name": "Furnizor Demo SRL", "property_account_payable_id": payable.id})
        cls.carrier = env["res.partner"].create(
            {"name": "Transportator Demo SRL", "property_account_payable_id": payable.id}
        )
        # comanda de achiziție -> recepția -> factura furnizorului de marfă
        cls.purchase_order = env["purchase.order"].create(
            {
                "partner_id": cls.vendor.id,
                "order_line": [
                    Command.create({"product_id": cls.product.id, "product_qty": 10.0, "price_unit": 100.0})
                ],
            }
        )
        cls.purchase_order.button_confirm()
        cls.receipt = cls.purchase_order.picking_ids
        cls.receipt.move_ids._set_quantity_done(10.0)
        cls.receipt.with_context(demo_mode=True).button_validate()
        cls.receipt_note = cls.receipt.move_ids.account_move_id[:1]
        cls.purchase_order.action_create_invoice()
        cls.goods_bill = cls.purchase_order.invoice_ids
        cls.goods_bill.write(
            {
                "invoice_date": fields.Date.today(),
                "ref": "FF-1001",
                "invoice_payment_term_id": env.ref("account.account_payment_term_immediate").id,
            }
        )
        cls.goods_bill.action_post()
        # facturile transportatorului (linie cu produs „Este cost adițional") -> costuri adiționale
        cls.carrier_bill_standard = cls._carrier_bill("FT-2001")
        cls.landed_standard = cls._landed_cost_from_bill(cls.carrier_bill_standard)
        company.write(
            {"landed_cost_method": "intermediary", "landed_cost_intermediary_account_id": cls.account_inter.id}
        )
        cls.carrier_bill_routed = cls._carrier_bill("FT-2002")
        cls.landed_routed = cls._landed_cost_from_bill(cls.carrier_bill_routed)

    @classmethod
    def _carrier_bill(cls, ref):
        env = cls.env
        bill = env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.carrier.id,
                "invoice_date": fields.Date.today(),
                "ref": ref,
                "invoice_payment_term_id": env.ref("account.account_payment_term_immediate").id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": cls.cost_product.id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": cls.account_transport.id,
                            "is_landed_costs_line": True,
                            "tax_ids": [Command.set(env.company.account_purchase_tax_id.ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    @classmethod
    def _landed_cost_from_bill(cls, bill):
        """Ca operatorul: butonul de pe factura transportatorului, apoi recepția în câmpul Transferuri."""
        landed = cls.env["stock.landed.cost"].browse(bill.button_create_landed_costs()["res_id"])
        landed.write({"picking_ids": [Command.set(cls.receipt.ids)], "account_journal_id": cls.stock_journal.id})
        landed.cost_lines.split_method = "by_quantity"
        landed.compute_landed_cost()
        landed.button_validate()
        return landed

    @classmethod
    def _ro_account(cls, code_like, name, code, account_type):
        account = cls.env["account.account"].search(
            [("code", "=like", code_like), ("company_ids", "in", [cls.env.company.id])], order="code", limit=1
        )
        return account or cls.env["account.account"].create({"name": name, "code": code, "account_type": account_type})

    def _dr_cr(self, move):
        return sorted((line.account_id.code[:6], round(line.debit, 2), round(line.credit, 2)) for line in move.line_ids)

    def _form(self, record, name, **kw):
        return {
            "path": f"/web?debug=0#id={record.id}&model={record._name}&view_type=form",
            "name": name,
            "wait": ".o_form_view",
            "settle": 2500,
            **kw,
        }

    def _shots(self):
        action = self.env.ref("stock.action_stock_config_settings").id
        return [
            {
                "path": f"/web?debug=0#action={action}&view_type=form",
                "name": "01_settings_landed_cost.png",
                "wait": ".o_form_view",
                "eval": "document.querySelector('[name=landed_cost_method]').scrollIntoView({block: 'center'})",
                "highlight": ["div[name='landed_cost_method']", "div[name='landed_cost_intermediary_account_id']"],
                "settle": 3000,
            },
            self._form(self.purchase_order, "02_purchase_order.png"),
            self._form(self.receipt, "03_receipt.png"),
            self.account_move_shot(self.receipt_note, "04_receipt_note.png"),
            self._form(self.goods_bill, "05_goods_bill.png"),
            self._form(
                self.carrier_bill_standard,
                "06_transport_bill_button.png",
                highlight=["button[name='button_create_landed_costs']"],
            ),
            self._form(self.landed_standard, "07_landed_cost_form.png"),
            self.account_move_shot(self.landed_standard.account_move_id, "08_note_standard.png"),
            self.account_move_shot(self.landed_routed.account_move_id, "09_note_intermediary.png"),
        ]

    def test_capture_fise(self):
        # notele din capturi trebuie să fie cele descrise în fișă
        self.assertEqual(
            self._dr_cr(self.receipt_note), sorted([("371000", 1000.0, 0.0), (self.account_src.code[:6], 0.0, 1000.0)])
        )
        self.assertEqual(
            self._dr_cr(self.landed_standard.account_move_id), [("371000", 50.0, 0.0), ("624000", 0.0, 50.0)]
        )
        self.assertEqual(
            self._dr_cr(self.landed_routed.account_move_id),
            [("371000", 50.0, 0.0), ("473900", 0.0, 50.0), ("473900", 50.0, 0.0), ("624000", 0.0, 50.0)],
        )
        self.capture_screenshots(self._shots())

    def test_capture_usage(self):
        self.capture_screenshots(self._shots(), lang="en_US")
