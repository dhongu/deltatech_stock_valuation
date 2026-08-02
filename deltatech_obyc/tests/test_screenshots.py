# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_obyc` (matrice OBYC de
# determinare conturi), generate în timpul testelor, în limba RO, pe planul de conturi RO
# (setup_country("ro")).
#
# Seed determinist: companie RO cu arie de evaluare proprie (cu Stock Journal dedicat), o
# clasă de evaluare, un account modifier, o matrice de reguli OBYC și un produs cu Valuation
# Class. Pentru notele contabile reale se validează o recepție de furnizor (cheia
# stock_receipt) și un retur la furnizor cu Storno accounting activ (înregistrare în roșu).
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -u deltatech_obyc \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.l10n_ro_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestObycScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_obyc"

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

        # --- Conturi din planul RO pentru regulile OBYC -------------------------------
        # 371 Mărfuri (cont de evaluare), 401 Furnizori intermediar (sursă), 607 Cheltuieli
        cls.account_valuation = cls._ro_account("371%", "Mărfuri", "371000", "asset_current")
        cls.account_src = cls._ro_account("408%", "Furnizori - facturi nesosite", "408000", "liability_current")
        cls.account_dest = cls._ro_account("607%", "Cheltuieli privind mărfurile", "607000", "expense")

        # --- Date de bază OBYC --------------------------------------------------------
        cls.valuation_class = env["product.valuation.class"].create({"name": "Marfă", "code": "MF"})
        cls.account_modifier = env["account.modifier"].create({"name": "Magazin central", "code": "MAG"})

        # jurnal de stoc dedicat ariei de evaluare (secțiunea 7.1 din fișă)
        cls.stock_journal = env["account.journal"].create(
            {"name": "Stoc - Magazin central", "code": "STMC", "type": "general", "company_id": company.id}
        )

        # aria de evaluare la nivel de companie, cu jurnal propriu
        company.use_valuation_area = True
        company.valuation_area_level = "company"
        company.set_stock_valuation_at_company_level()
        cls.valuation_area = company.valuation_area_id
        cls.valuation_area.write({"name": "Magazin central", "code": "MAG", "stock_journal_id": cls.stock_journal.id})

        # --- Matricea de reguli OBYC --------------------------------------------------
        det = env["product.account.determination"]
        for key, src, dest in [
            ("stock_receipt", cls.account_src, cls.account_dest),
            ("stock_delivery", cls.account_dest, cls.account_src),
            ("return_to_supplier", False, cls.account_src),
            ("return_from_customer", cls.account_src, cls.account_dest),
        ]:
            det.create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": company.id,
                    "acc_src_id": src and src.id,
                    "acc_dest_id": dest.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )
        # o regulă cu account modifier completat, ca matricea să arate coloana folosită
        cls.rule_modifier = det.create(
            {
                "transaction_key": "internal_transfer",
                "account_modifier_id": cls.account_modifier.id,
                "valuation_class_id": cls.valuation_class.id,
                "valuation_area_id": cls.valuation_area.id,
                "company_id": company.id,
                "acc_src_id": cls.account_valuation.id,
                "acc_dest_id": cls.account_valuation.id,
                "acc_valuation_id": cls.account_valuation.id,
            }
        )

        # --- Categorie real_time + produs cu Valuation Class --------------------------
        cls.categ = env["product.category"].create(
            {
                "name": "Mărfuri OBYC",
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": cls.account_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product = cls.product_a
        cls.product.write(
            {
                "name": "Marfă demo OBYC",
                "is_storable": True,
                "categ_id": cls.categ.id,
                "valuation_class_id": cls.valuation_class.id,
                "standard_price": 100.0,
            }
        )

        # --- Locații / tipuri de picking (din depozitul companiei RO) -----------------
        warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if not warehouse:
            warehouse = env["stock.warehouse"].create({"name": "Depozit RO", "code": "RO", "company_id": company.id})
        cls.supplier_location = env.ref("stock.stock_location_suppliers")
        cls.stock_location = warehouse.lot_stock_id
        cls.picking_type_in = warehouse.in_type_id

        # --- Note contabile reale prin OBYC ------------------------------------------
        # 1) Recepție furnizor → NC OBYC (Dr 371 / Cr cont sursă), pe jurnalul ariei
        cls.receipt_picking = cls._make_receipt(qty=10.0)
        cls.move_receipt = cls.receipt_picking.move_ids.account_move_id[:1]

        # 2) Retur la furnizor cu Storno activ → aceleași conturi, sume negative (roșu)
        cls.move_storno = cls._make_storno_return(cls.receipt_picking, qty=5.0)

        # --- Acțiuni -----------------------------------------------------------------
        cls.act_determination = env.ref("deltatech_obyc.action_product_account_determination").id
        cls.act_valuation_class = env.ref("deltatech_obyc.action_product_valuation_class").id
        cls.act_modifier = env.ref("deltatech_obyc.action_account_modifier").id

    # ---------------------------------------------------------------------------------
    # Helperi de seed
    # ---------------------------------------------------------------------------------
    @classmethod
    def _ro_account(cls, code_like, name, code, account_type):
        env = cls.env
        account = env["account.account"].search(
            [("code", "=like", code_like), ("company_ids", "in", [env.company.id])], order="code", limit=1
        )
        if not account:
            account = env["account.account"].create({"name": name, "code": code, "account_type": account_type})
        return account

    @classmethod
    def _validate_picking(cls, picking):
        picking.action_confirm()
        picking.move_ids._set_quantity_done(picking.move_ids[0].product_uom_qty)
        result = picking.with_context(demo_mode=True).button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.immediate.transfer":
            cls.env[result["res_model"]].browse(result["res_id"]).process()

    @classmethod
    def _make_receipt(cls, qty=10.0):
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": cls.picking_type_in.id,
                "location_id": cls.supplier_location.id,
                "location_dest_id": cls.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": qty,
                            "product_uom": cls.product.uom_id.id,
                            "location_id": cls.supplier_location.id,
                            "location_dest_id": cls.stock_location.id,
                        }
                    )
                ],
            }
        )
        cls._validate_picking(picking)
        return picking

    @classmethod
    def _make_storno_return(cls, picking, qty=5.0):
        cls.env.company.account_storno = True
        return_wizard = (
            cls.env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking").create({})
        )
        return_wizard.product_return_moves.quantity = qty
        action = return_wizard.action_create_returns()
        return_picking = cls.env["stock.picking"].browse(action["res_id"])
        cls._validate_picking(return_picking)
        return return_picking.move_ids.account_move_id[:1]

    # ---------------------------------------------------------------------------------
    # Capturi
    # ---------------------------------------------------------------------------------
    def test_capture_fise(self):
        # ascunde butonul „Nou(ă)" din control panel (consultăm înregistrări existente)
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
            # 1. Matricea OBYC: lista de reguli product.account.determination
            {
                "path": f"/web?debug=0#action={self.act_determination}&view_type=list",
                "name": "01_account_determination_matrix.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 2. Formularul unei reguli OBYC (condiții + conturi sursă/destinație/evaluare)
            {
                "path": f"/web?debug=0#id={self.rule_modifier.id}&model=product.account.determination&view_type=form",
                "name": "02_account_determination_form.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "settle": 2000,
            },
            # 3. Lista claselor de evaluare (Evaluation Class)
            {
                "path": f"/web?debug=0#action={self.act_valuation_class}&view_type=list",
                "name": "03_valuation_class_list.png",
                "wait": ".o_list_view",
                "settle": 2000,
            },
            # 4. Aria de evaluare cu Stock Journal dedicat (jurnalul OBYC pe arie)
            {
                "path": f"/web?debug=0#id={self.valuation_area.id}&model=valuation.area&view_type=form",
                "name": "04_valuation_area_journal.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": ["field[name='stock_journal_id'], div[name='stock_journal_id']"],
                "settle": 2000,
            },
            # 5. Produsul cu Valuation Class completat (tab Contabilitate)
            {
                "path": f"/web?debug=0#id={self.product.product_tmpl_id.id}&model=product.template&view_type=form",
                "name": "05_product_valuation_class.png",
                "wait": ".o_form_view",
                "click_tab": "Contabilitate",
                "eval": hide_new_btn_js,
                "highlight": ["field[name='valuation_class_id'], div[name='valuation_class_id']"],
                "settle": 2500,
            },
            # 6. Nota OBYC a recepției (Journal Items: Dr 371 / Cr cont sursă, pe jurnalul ariei)
            self.account_move_shot(self.move_receipt, "06_stock_move_obyc_entry.png"),
            # 7. Nota de storno la retur (aceleași conturi, sume negative — în roșu)
            self.account_move_shot(self.move_storno, "07_storno_return.png"),
        ]
        self.capture_screenshots(shots)
