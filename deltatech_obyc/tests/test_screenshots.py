# ©  2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant a modulului `deltatech_obyc` (matrice OBYC de
# determinare conturi), generate în timpul testelor, în limba RO, pe planul de conturi RO
# (setup_country("ro")).
#
# Seed determinist: companie RO cu arie de evaluare proprie (cu Stock Journal dedicat), o
# clasă de evaluare, un account modifier, o matrice de reguli OBYC și un produs cu Valuation
# Class. Pentru notele contabile reale se validează: o recepție de furnizor (cheia
# stock_receipt), un retur la furnizor cu Storno accounting activ (înregistrare în roșu), o
# livrare la client (cheia stock_delivery: costul mărfii vândute se înregistrează la livrare),
# factura de vânzare (doar venit + TVA, fără linii de cost) și un cost de achiziție (landed
# cost) pe o a doua recepție.
#
# Convenția din cod pentru notele de stoc: dacă regula are Cont sursă → Dr Cont de evaluare /
# Cr Cont sursă; altfel → Dr Cont destinație / Cr Cont de evaluare.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -u deltatech_obyc \
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
        # 371 Mărfuri (cont de evaluare), 408 Furnizori - facturi nesosite, 607 Cheltuieli
        # privind mărfurile, 707 Venituri din vânzarea mărfurilor
        cls.account_valuation = cls._ro_account("371%", "Mărfuri", "371000", "asset_current")
        cls.account_src = cls._ro_account("408%", "Furnizori - facturi nesosite", "408000", "liability_current")
        cls.account_dest = cls._ro_account("607%", "Cheltuieli privind mărfurile", "607000", "expense")
        cls.account_income = cls._ro_account("707%", "Venituri din vânzarea mărfurilor", "707000", "income")

        # --- Date de bază OBYC --------------------------------------------------------
        cls.valuation_class = env["product.valuation.class"].create({"name": "Marfă", "code": "MF"})
        cls.account_modifier = env["account.modifier"].create({"name": "Transferuri interne", "code": "INT"})

        # jurnal de stoc dedicat ariei de evaluare (secțiunea 7.1 din fișă)
        cls.stock_journal = env["account.journal"].create(
            {"name": "Stoc - Magazin central", "code": "STMC", "type": "general", "company_id": company.id}
        )

        # aria de evaluare la nivel de companie, cu jurnal propriu
        # (doar câmpurile din deltatech_valuation_area, dependența modulului — fără
        # deltatech_stock_valuation, care nu e necesar pentru OBYC)
        cls.valuation_area = env["valuation.area"].create(
            {
                "name": "Magazin central",
                "code": "MAG",
                "company_id": company.id,
                "stock_journal_id": cls.stock_journal.id,
            }
        )
        company.write({"use_valuation_area": True, "valuation_area_id": cls.valuation_area.id})

        # --- Matricea de reguli OBYC --------------------------------------------------
        # (cheie, cont sursă, cont destinație, cont de evaluare)
        #   recepție:            Dr 371 / Cr 408  (sursă completată)
        #   retur la furnizor:   Dr 408 / Cr 371  (fără sursă) — cu storno: Dr 371 −V / Cr 408 −V
        #   livrare:             Dr 607 / Cr 371  (fără sursă) — costul la livrare
        #   retur de la client:  Dr 371 / Cr 607  (sursă completată)
        #   venit (factura):     Cr 707 — 707 pus și ca cont de evaluare, ca linia facturii să
        #                        nu ajungă pe alt cont (OBYC-001 din readme/bugs.md)
        #   cost de achiziție:   Dr 371 / Cr contul liniei de cost
        det = env["product.account.determination"]
        for key, src, dest, val in [
            ("stock_receipt", cls.account_src, False, cls.account_valuation),
            ("return_to_supplier", False, cls.account_src, cls.account_valuation),
            ("stock_delivery", False, cls.account_dest, cls.account_valuation),
            ("return_from_customer", cls.account_dest, False, cls.account_valuation),
            ("stock_income", cls.account_income, cls.account_income, cls.account_income),
            ("landed_cost", False, False, cls.account_valuation),
        ]:
            det.create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": company.id,
                    "acc_src_id": src and src.id,
                    "acc_dest_id": dest and dest.id,
                    "acc_valuation_id": val.id,
                }
            )
        # o regulă cu account modifier completat, ca matricea să arate coloana folosită;
        # transferul în aceeași arie nu schimbă valoarea stocului: conturi goale → fără notă
        cls.rule_modifier = det.create(
            {
                "transaction_key": "internal_transfer",
                "account_modifier_id": cls.account_modifier.id,
                "valuation_class_id": cls.valuation_class.id,
                "valuation_area_id": cls.valuation_area.id,
                "company_id": company.id,
            }
        )
        cls.rule_delivery = det.search(
            [("transaction_key", "=", "stock_delivery"), ("valuation_class_id", "=", cls.valuation_class.id)], limit=1
        )

        # --- Categorie real_time + produs cu Valuation Class --------------------------
        cls.categ = env["product.category"].create(
            {
                "name": "Mărfuri OBYC",
                "property_valuation": "real_time",
                "property_cost_method": "average",  # landed cost cere FIFO sau cost mediu
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
                # conturile standard ale produsului nu sunt folosite de OBYC; le aliniem cu
                # matricea ca să nu deruteze în captura produsului
                "property_account_income_id": cls.account_income.id,
                "property_account_expense_id": cls.account_dest.id,
            }
        )
        # separat, după schimbarea categoriei (cost mediu), ca prețul să nu fie suprascris
        cls.product.standard_price = 100.0

        # --- Locații / tipuri de picking (din depozitul companiei RO) -----------------
        warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if not warehouse:
            warehouse = env["stock.warehouse"].create({"name": "Depozit RO", "code": "MAG", "company_id": company.id})
        else:
            # referințe lizibile în capturi (MAG/IN/00001 în loc de compa/IN/00001)
            warehouse.code = "MAG"
        cls.supplier_location = env.ref("stock.stock_location_suppliers")
        cls.stock_location = warehouse.lot_stock_id
        cls.customer_location = env.ref("stock.stock_location_customers")
        cls.picking_type_in = warehouse.in_type_id
        cls.picking_type_out = warehouse.out_type_id
        cls.supplier = cls.partner_b
        cls.supplier.name = "Furnizor Demo SRL"
        cls.customer = cls.partner_a
        cls.customer.name = "Client Demo SRL"

        # --- Note contabile reale prin OBYC ------------------------------------------
        # 1) Recepție furnizor → NC OBYC (Dr 371 / Cr cont sursă), pe jurnalul ariei
        cls.receipt_picking = cls._make_receipt(qty=10.0)
        cls.move_receipt = cls.receipt_picking.move_ids.account_move_id[:1]

        # 2) Retur la furnizor cu Storno activ → aceleași conturi, sume negative (roșu)
        cls.move_storno = cls._make_storno_return(cls.receipt_picking, qty=5.0)

        # 3) Livrare la client → costul mărfii vândute la livrare (Dr 607 / Cr 371)
        cls.delivery_picking = cls._make_picking(
            cls.picking_type_out, cls.stock_location, cls.customer_location, 2.0, cls.customer
        )
        cls.move_delivery = cls.delivery_picking.move_ids.account_move_id[:1]

        # 4) Factura de vânzare → doar venit + TVA (Dr 4111 / Cr 707 + 4427), fără linii de cost
        cls.invoice = cls._make_sale_invoice(qty=2.0, price=150.0)

        # 5) Cost de achiziție (transport) pe o a doua recepție → Dr 371 / Cr contul liniei de cost
        cls.receipt_lc = cls._make_receipt(qty=10.0)
        cls.landed_cost = cls._make_landed_cost(cls.receipt_lc, amount=50.0)
        cls.move_landed_cost = cls.landed_cost.account_move_id

        # --- Acțiuni -----------------------------------------------------------------
        cls.act_determination = env.ref("deltatech_obyc.action_product_account_determination").id
        cls.act_valuation_class = env.ref("deltatech_obyc.action_product_valuation_class").id
        cls.act_modifier = env.ref("deltatech_obyc.action_account_modifier").id
        cls.act_out_invoice = env.ref("account.action_move_out_invoice_type").id

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
    def _make_picking(cls, picking_type, location, location_dest, qty, partner):
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "partner_id": partner.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": qty,
                            "product_uom": cls.product.uom_id.id,
                            "location_id": location.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                ],
            }
        )
        cls._validate_picking(picking)
        return picking

    @classmethod
    def _make_receipt(cls, qty=10.0):
        return cls._make_picking(cls.picking_type_in, cls.supplier_location, cls.stock_location, qty, cls.supplier)

    @classmethod
    def _make_sale_invoice(cls, qty, price):
        company = cls.env.company
        tax = company.account_sale_tax_id
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.customer.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "quantity": qty,
                            "price_unit": price,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    @classmethod
    def _make_landed_cost(cls, picking, amount):
        cost_product = cls.env["product.product"].create(
            {"name": "Transport marfă", "type": "service", "landed_cost_ok": True}
        )
        landed_cost = cls.env["stock.landed.cost"].create(
            {
                "picking_ids": [Command.set(picking.ids)],
                "account_journal_id": cls.stock_journal.id,
                "cost_lines": [
                    Command.create(
                        {
                            "name": "Transport marfă",
                            "product_id": cost_product.id,
                            "price_unit": amount,
                            "split_method": "by_quantity",
                            "account_id": cls.account_src.id,
                        }
                    )
                ],
            }
        )
        landed_cost.compute_landed_cost()
        landed_cost.button_validate()
        return landed_cost

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
    def _dr_cr(self, move):
        return sorted((line.account_id.code[:3], round(line.debit, 2), round(line.credit, 2)) for line in move.line_ids)

    def test_capture_fise(self):
        # notele din capturi trebuie să fie cele descrise în fișă (altfel captura ar minți)
        self.assertEqual(self._dr_cr(self.move_receipt), [("371", 1000.0, 0.0), ("408", 0.0, 1000.0)])
        self.assertEqual(self._dr_cr(self.move_storno), [("371", -500.0, 0.0), ("408", 0.0, -500.0)])
        self.assertEqual(self._dr_cr(self.move_delivery), [("371", 0.0, 200.0), ("607", 200.0, 0.0)])
        self.assertFalse(self.invoice.line_ids.filtered(lambda line: line.display_type == "cogs"))
        self.assertEqual(
            [code for code, _dr, _cr in self._dr_cr(self.invoice)], ["411", "442", "707"], self._dr_cr(self.invoice)
        )
        self.assertEqual(self._dr_cr(self.move_landed_cost), [("371", 50.0, 0.0), ("408", 0.0, 50.0)])
        self.assertEqual(self.move_delivery.journal_id, self.stock_journal)

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
            # 2. Formularul regulii de livrare (condiții + conturi): Cont sursă gol →
            #    Dr Cont destinație (607) / Cr Cont de evaluare (371)
            {
                "path": (
                    f"/web?debug=0#action={self.act_determination}&id={self.rule_delivery.id}"
                    "&model=product.account.determination&view_type=form"
                ),
                "name": "02_account_determination_form.png",
                "wait": ".o_form_view",
                "eval": hide_new_btn_js,
                "highlight": [
                    "div[name='acc_src_id']",
                    "div[name='acc_dest_id']",
                    "div[name='acc_valuation_id']",
                ],
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
            # 8. Nota livrării: costul mărfii vândute la livrare (Dr 607 / Cr 371)
            self.account_move_shot(self.move_delivery, "08_delivery_cogs_entry.png"),
            # 9. Factura de vânzare: doar venit + TVA, fără linii de cost
            {
                **self.account_move_shot(self.invoice, "09_sale_invoice_no_cogs.png"),
                # deschisă din Facturare → Clienți → Facturi (breadcrumb „Facturi")
                "url": f"action={self.act_out_invoice}&id={self.invoice.id}&model=account.move&view_type=form",
            },
            # 10. Nota costului de achiziție (landed cost): Dr 371 / Cr contul liniei de cost
            self.account_move_shot(self.move_landed_cost, "10_landed_cost_entry.png"),
        ]
        self.capture_screenshots(shots)
