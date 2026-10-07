# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# Notele contabile OBYC (conturi Dr/Cr, sume, cantități semnate) pe scenariile de bază:
# recepție, livrare, retur de la client (negru și storno), cost de achiziție (landed cost)
# și factura de vânzare.

from odoo import Command
from odoo.tests import tagged

from .test_common import TestCommon


@tagged("post_install", "-at_install")
class TestObycEntries(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_stock_valuation = cls.env["account.account"].create(
            {"name": "Stock Valuation Cat", "code": "SVC003", "account_type": "asset_current"}
        )
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product.standard_price = 100.0
        cls.account_customer = cls.env["account.account"].create(
            {"name": "Test Customer Return Account", "code": "TCR001", "account_type": "asset_current"}
        )
        cls.account_income = cls.env["account.account"].create(
            {"name": "Test Income", "code": "TINC01", "account_type": "income"}
        )
        cls.account_income_debit = cls.env["account.account"].create(
            {"name": "Test Income Debit", "code": "TINCD1", "account_type": "asset_current"}
        )
        cls.account_lc_expense = cls.env["account.account"].create(
            {"name": "Test Landed Cost Expense", "code": "TLCE01", "account_type": "expense"}
        )
        cls.account_inventory_gain = cls.env["account.account"].create(
            {"name": "Test Inventory Gain", "code": "TINVG1", "account_type": "income_other"}
        )
        cls.account_inventory_loss = cls.env["account.account"].create(
            {"name": "Test Inventory Loss", "code": "TINVL1", "account_type": "expense"}
        )
        # recepție: Dr valuation / Cr src; livrare (doar acc_dest): Dr dest / Cr valuation;
        # retur de la client: Dr valuation / Cr src; cost de achiziție: Dr valuation;
        # venit (factura de vânzare): Cr dest; plus de inventar: Dr valuation / Cr src;
        # minus de inventar: Dr dest / Cr valuation
        for key, src, dest in [
            ("stock_receipt", cls.account_src, False),
            ("stock_delivery", False, cls.account_dest),
            ("return_from_customer", cls.account_customer, False),
            ("landed_cost", False, False),
            ("stock_income", cls.account_income_debit, cls.account_income),
            ("inventory_adjustment_plus", cls.account_inventory_gain, False),
            ("inventory_adjustment_minus", False, cls.account_inventory_loss),
        ]:
            cls.env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": cls.env.company.id,
                    "acc_src_id": src and src.id,
                    "acc_dest_id": dest and dest.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

        # compania default din baza de test nu are plan de conturi — contul de creanțe
        # și jurnalul de vânzări se creează explicit
        cls.account_receivable = cls.env["account.account"].create(
            {"name": "Test Receivable", "code": "TREC02", "account_type": "asset_receivable", "reconcile": True}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Customer OBYC", "property_account_receivable_id": cls.account_receivable.id}
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {"name": "Test Sale Journal", "code": "TSJ2", "type": "sale", "company_id": cls.env.company.id}
        )
        cls.account_payable = cls.env["account.account"].create(
            {"name": "Test Payable", "code": "TPAY02", "account_type": "liability_payable", "reconcile": True}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Vendor OBYC", "property_account_payable_id": cls.account_payable.id}
        )
        cls.purchase_journal = cls.env["account.journal"].create(
            {"name": "Test Purchase Journal", "code": "TPJ2", "type": "purchase", "company_id": cls.env.company.id}
        )

    def _picking(self, picking_type, location, location_dest, qty):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom": self.product.uom_id.id,
                            "location_id": location.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                ],
            }
        )
        self._validate(picking)
        return picking

    def _validate(self, picking):
        picking.action_confirm()
        picking.move_ids._set_quantity_done(picking.move_ids[0].product_uom_qty)
        picking.with_context(demo_mode=True).button_validate()

    def _sorted_lines(self, account_move):
        return account_move.line_ids.sorted(lambda line: (line.account_id.code, line.debit, line.credit))

    def _lines(self, picking):
        account_move = picking.move_ids.account_move_id
        self.assertEqual(len(account_move), 1)
        self.assertEqual(account_move.state, "posted")
        self.assertEqual(account_move.journal_id, self.stock_journal)
        return self._sorted_lines(account_move)

    def _receipt(self, qty):
        return self._picking(self.picking_type_in, self.supplier_location, self.stock_location, qty)

    def _delivery(self, qty):
        return self._picking(self.picking_type_out, self.stock_location, self.customer_location, qty)

    def _customer_return(self, picking, qty):
        return_wizard = (
            self.env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking").create({})
        )
        return_wizard.product_return_moves.quantity = qty
        action = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(action["res_id"])
        self._validate(return_picking)
        return return_picking

    def _invoice(self, move_type, lines):
        is_sale = move_type.startswith("out_")
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "invoice_date": "2026-01-15",
                "partner_id": (self.partner if is_sale else self.vendor).id,
                "journal_id": (self.sale_journal if is_sale else self.purchase_journal).id,
                "invoice_line_ids": [
                    Command.create({"product_id": product.id, "quantity": qty, "price_unit": price, "tax_ids": []})
                    for product, qty, price in lines
                ],
            }
        )

    def _out_invoice(self, lines):
        return self._invoice("out_invoice", lines)

    def test_01_receipt(self):
        lines = self._lines(self._receipt(10.0))
        self.assertRecordValues(
            lines,
            [
                {"account_id": self.account_src.id, "debit": 0.0, "credit": 1000.0, "quantity": -10.0},
                {"account_id": self.account_valuation.id, "debit": 1000.0, "credit": 0.0, "quantity": 10.0},
            ],
        )

    def test_02_delivery(self):
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertAlmostEqual(delivery.move_ids.value, 400.0)
        self.assertRecordValues(
            self._lines(delivery),
            [
                {"account_id": self.account_dest.id, "debit": 400.0, "credit": 0.0, "quantity": 4.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 400.0, "quantity": -4.0},
            ],
        )

    def test_03_customer_return(self):
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertRecordValues(
            self._lines(self._customer_return(delivery, 1.0)),
            [
                {"account_id": self.account_customer.id, "debit": 0.0, "credit": 100.0, "quantity": -1.0},
                {"account_id": self.account_valuation.id, "debit": 100.0, "credit": 0.0, "quantity": 1.0},
            ],
        )

    def test_04_customer_return_storno(self):
        self.env.company.account_storno = True
        self._receipt(10.0)
        delivery = self._delivery(4.0)
        self.assertRecordValues(
            self._lines(self._customer_return(delivery, 1.0)),
            [
                {"account_id": self.account_customer.id, "debit": -100.0, "credit": 0.0, "quantity": 1.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": -100.0, "quantity": -1.0},
            ],
        )

    def test_05_landed_cost(self):
        """Costul de achiziție pe o recepție OBYC: Dr contul de stoc din regula
        `landed_cost` / Cr contul liniei de cost. Înainte de fix, validarea cădea cu
        `AttributeError: 'int' object has no attribute 'id'` (conturile întoarse ca id-uri)."""
        receipt = self._receipt(10.0)
        cost_product = self.env["product.product"].create(
            {"name": "Transport", "type": "service", "landed_cost_ok": True}
        )
        landed_cost = self.env["stock.landed.cost"].create(
            {
                "picking_ids": [Command.set(receipt.ids)],
                "account_journal_id": self.stock_journal.id,
                "cost_lines": [
                    Command.create(
                        {
                            "name": "Transport",
                            "product_id": cost_product.id,
                            "price_unit": 50.0,
                            "split_method": "by_quantity",
                            "account_id": self.account_lc_expense.id,
                        }
                    )
                ],
            }
        )
        landed_cost.compute_landed_cost()
        landed_cost.button_validate()
        self.assertEqual(landed_cost.state, "done")
        self.assertEqual(landed_cost.account_move_id.state, "posted")
        self.assertRecordValues(
            self._sorted_lines(landed_cost.account_move_id),
            [
                {"account_id": self.account_lc_expense.id, "debit": 0.0, "credit": 50.0},
                {"account_id": self.account_valuation.id, "debit": 50.0, "credit": 0.0},
            ],
        )
        self.assertAlmostEqual(receipt.move_ids.value, 1050.0)

    def test_06_sale_invoice(self):
        """Factura de vânzare pe un produs OBYC evaluat în timp real: doar venitul (cheia
        `stock_income`), fără linii COGS — costul s-a înregistrat deja la livrare
        (cheia `stock_delivery`). Înainte de fix, postarea cădea cu „Transaction key is
        not defined"."""
        self._receipt(10.0)
        delivery = self._delivery(2.0)
        invoice = self._out_invoice([(self.product, 2.0, 150.0)])
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(invoice.line_ids.filtered(lambda line: line.display_type == "cogs"))
        self.assertRecordValues(
            self._sorted_lines(invoice),
            [
                {"account_id": self.account_income.id, "debit": 0.0, "credit": 300.0},
                {"account_id": self.account_receivable.id, "debit": 300.0, "credit": 0.0},
            ],
        )
        # costul mărfii vândute rămâne doar pe nota livrării, o singură dată
        self.assertRecordValues(
            self._lines(delivery),
            [
                {"account_id": self.account_dest.id, "debit": 200.0, "credit": 0.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 200.0},
            ],
        )

    def test_07_sale_invoice_two_obyc_products(self):
        """Factură cu două produse OBYC din clase de evaluare diferite: fiecare linie își
        ia contul din regula clasei ei. Înainte de fix, `_compute_account_id` citea
        `self.product_id` (toate liniile) → „Expected singleton"."""
        valuation_class_b = self.env["product.valuation.class"].create({"name": "Test Class B", "code": "TCB"})
        account_income_b = self.env["account.account"].create(
            {"name": "Test Income B", "code": "TINC02", "account_type": "income"}
        )
        self.env["product.account.determination"].create(
            {
                "transaction_key": "stock_income",
                "valuation_class_id": valuation_class_b.id,
                "valuation_area_id": self.valuation_area.id,
                "company_id": self.env.company.id,
                "acc_dest_id": account_income_b.id,
                "acc_valuation_id": self.account_valuation.id,
            }
        )
        product_b = self.env["product.product"].create(
            {
                "name": "Test Product B",
                "is_storable": True,
                "categ_id": self.product_category.id,
                "valuation_class_id": valuation_class_b.id,
            }
        )
        invoice = self._out_invoice([(self.product, 1.0, 100.0), (product_b, 2.0, 40.0)])
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertRecordValues(
            self._sorted_lines(invoice),
            [
                {"account_id": self.account_income.id, "product_id": self.product.id, "debit": 0.0, "credit": 100.0},
                {"account_id": account_income_b.id, "product_id": product_b.id, "debit": 0.0, "credit": 80.0},
                {"account_id": self.account_receivable.id, "product_id": False, "debit": 180.0, "credit": 0.0},
            ],
        )

    def test_08_customer_credit_note(self):
        """Nota de credit către client folosește același cont de venit ca factura
        (`acc_dest_id` al regulii `stock_income`), cu partea inversată. Contul se alege
        la creare, fără recalcul (OBYC-001)."""
        credit_note = self._invoice("out_refund", [(self.product, 1.0, 150.0)])
        credit_note.action_post()
        self.assertRecordValues(
            self._sorted_lines(credit_note),
            [
                {"account_id": self.account_income.id, "debit": 150.0, "credit": 0.0},
                {"account_id": self.account_receivable.id, "debit": 0.0, "credit": 150.0},
            ],
        )

    def test_09_vendor_bill(self):
        """Factura de furnizor după recepție: linia de produs stinge contul de
        recepții nefacturate al regulii `stock_receipt` (`acc_src_id`), nu debitează
        din nou stocul. Înainte de fix, linia lua `acc_valuation_id` și stocul se
        dubla valoric (OBYC-001)."""
        receipt = self._receipt(10.0)
        bill = self._invoice("in_invoice", [(self.product, 10.0, 100.0)])
        bill.action_post()
        self.assertRecordValues(
            self._sorted_lines(bill),
            [
                {"account_id": self.account_payable.id, "debit": 0.0, "credit": 1000.0},
                {"account_id": self.account_src.id, "debit": 1000.0, "credit": 0.0},
            ],
        )
        # stocul rămâne debitat o singură dată, de nota recepției
        stock_lines = self.env["account.move.line"].search(
            [("account_id", "=", self.account_valuation.id), ("parent_state", "=", "posted")]
        )
        self.assertEqual(stock_lines.move_id, receipt.move_ids.account_move_id)
        self.assertEqual(sum(stock_lines.mapped("balance")), 1000.0)

    def test_10_vendor_credit_note(self):
        """Nota de credit de la furnizor folosește același cont ca factura
        (`acc_src_id` al regulii `stock_receipt`), cu partea inversată."""
        credit_note = self._invoice("in_refund", [(self.product, 2.0, 100.0)])
        credit_note.action_post()
        self.assertRecordValues(
            self._sorted_lines(credit_note),
            [
                {"account_id": self.account_payable.id, "debit": 200.0, "credit": 0.0},
                {"account_id": self.account_src.id, "debit": 0.0, "credit": 200.0},
            ],
        )

    def _inventory_move(self, counted_qty):
        """Ajustare de inventar pe locația de stoc; întoarce mișcarea generată."""
        quant = (
            self.env["stock.quant"]
            .with_context(inventory_mode=True)
            .create(
                {
                    "product_id": self.product.id,
                    "location_id": self.stock_location.id,
                    "inventory_quantity": counted_qty,
                }
            )
        )
        quant.action_apply_inventory()
        return self.env["stock.move"].search(
            [("product_id", "=", self.product.id), ("is_inventory", "=", True)], order="id desc", limit=1
        )

    def test_11_inventory_gain(self):
        """Plusul de inventar (locație de inventar → stoc) folosește regula
        `inventory_adjustment_plus`: Dr stoc / Cr contul de plus. Înainte de fix se folosea
        regula `inventory_adjustment_minus` (OBYC-005)."""
        move = self._inventory_move(5.0)
        self.assertEqual(move._compute_transaction_key(), "inventory_adjustment_plus")
        self.assertRecordValues(
            self._sorted_lines(move.account_move_id),
            [
                {"account_id": self.account_inventory_gain.id, "debit": 0.0, "credit": 500.0, "quantity": -5.0},
                {"account_id": self.account_valuation.id, "debit": 500.0, "credit": 0.0, "quantity": 5.0},
            ],
        )

    def test_12_inventory_loss(self):
        """Minusul de inventar (stoc → locație de inventar) folosește regula
        `inventory_adjustment_minus`: Dr contul de minus / Cr stoc (OBYC-005)."""
        self._receipt(10.0)
        move = self._inventory_move(7.0)
        self.assertEqual(move._compute_transaction_key(), "inventory_adjustment_minus")
        self.assertRecordValues(
            self._sorted_lines(move.account_move_id),
            [
                {"account_id": self.account_inventory_loss.id, "debit": 300.0, "credit": 0.0, "quantity": 3.0},
                {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 300.0, "quantity": -3.0},
            ],
        )

    def test_13_periodic_valuation_no_entry(self):
        """Produs cu clasă de evaluare într-o categorie cu evaluare periodică: recepția nu
        generează notă OBYC, ca în nucleu. Înainte de fix nota se crea oricum (OBYC-006)."""
        self.product_category.property_valuation = "periodic"
        receipt = self._receipt(10.0)
        self.assertEqual(receipt.state, "done")
        self.assertFalse(receipt.move_ids.account_move_id)

    def test_14_consumable_without_rules(self):
        """Produs consumabil (nestocabil) cu o clasă de evaluare fără reguli: livrarea se
        validează fără notă. Înainte de fix validarea cădea cu „No account determination
        rule found" (OBYC-006)."""
        valuation_class = self.env["product.valuation.class"].create({"name": "Test Class C", "code": "TCC"})
        consumable = self.env["product.product"].create(
            {
                "name": "Test Consumable",
                "type": "consu",
                "is_storable": False,
                "categ_id": self.product_category.id,
                "valuation_class_id": valuation_class.id,
            }
        )
        self.product = consumable
        delivery = self._delivery(2.0)
        self.assertEqual(delivery.state, "done")
        self.assertFalse(delivery.move_ids.account_move_id)

    def test_15_owner_stock_no_entry(self):
        """Marfă primită în custodie (proprietar terț): nucleul nu o evaluează, deci nici
        OBYC nu face notă. Înainte de fix se posta o notă cu valoare 0 (OBYC-006)."""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "owner_id": self.vendor.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 3.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        self._validate(picking)
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.move_line_ids.owner_id, self.vendor)
        self.assertFalse(picking.move_ids.account_move_id)

    def test_16_unmapped_locations_not_valued(self):
        """Mișcare între două locații pe care nici nucleul nu le evaluează (furnizor →
        inventar), fără cheie de tranzacție: se validează fără notă. Înainte de fix
        validarea cădea cu „Transaction key could not be determined" (OBYC-006)."""
        inventory_location = self.product.property_stock_inventory
        picking = self._picking(self.picking_type_in, self.supplier_location, inventory_location, 2.0)
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.move_ids.account_move_id)

    def _reclassification_setup(self):
        """Transfer intern cu modificator „Reclasificare": Dr 371 (nou) / Cr cont stoc (vechi)."""
        account_goods = self.env["account.account"].create(
            {"name": "Test Goods 371", "code": "TGD371", "account_type": "asset_current"}
        )
        modifier = self.env["account.modifier"].create({"name": "Reclasificare", "code": "RECLAS"})
        picking_type = self.env.ref("stock.picking_type_internal").copy(
            {"name": "Reclasificare", "sequence_code": "RCL", "account_modifier_id": modifier.id}
        )
        base = {
            "valuation_class_id": self.valuation_class.id,
            "valuation_area_id": self.valuation_area.id,
            "company_id": self.env.company.id,
        }
        self.env["product.account.determination"].create(
            {
                **base,
                "transaction_key": "internal_transfer",
                "account_modifier_id": modifier.id,
                "acc_src_id": self.account_valuation.id,
                "acc_valuation_id": account_goods.id,
            }
        )
        # transferul obișnuit: regula fără conturi, deci fără notă
        self.env["product.account.determination"].create({**base, "transaction_key": "internal_transfer"})
        location = self.env["stock.location"].create(
            {"name": "Reclass Shelf", "usage": "internal", "location_id": self.stock_location.id}
        )
        return account_goods, picking_type, location

    def test_08_internal_transfer_without_accounts_has_no_entry(self):
        _goods, _picking_type, location = self._reclassification_setup()
        self._receipt(10.0)
        transfer = self._picking(self.env.ref("stock.picking_type_internal"), self.stock_location, location, 10.0)
        self.assertFalse(transfer.move_ids.account_move_id)

    def test_09_internal_transfer_reclassification(self):
        """3028 → 371 pe un transfer intern, apoi livrarea scade 371."""
        account_goods, picking_type, location = self._reclassification_setup()
        self.env["product.account.determination"].search(
            [("transaction_key", "=", "stock_delivery")]
        ).acc_valuation_id = account_goods
        self._receipt(10.0)
        transfer = self._picking(picking_type, self.stock_location, location, 10.0)
        self.assertAlmostEqual(transfer.move_ids.value, 1000.0)
        self.assertRecordValues(
            self._lines(transfer),
            sorted(
                [
                    {"account_id": self.account_valuation.id, "debit": 0.0, "credit": 1000.0, "quantity": -10.0},
                    {"account_id": account_goods.id, "debit": 1000.0, "credit": 0.0, "quantity": 10.0},
                ],
                key=lambda v: self.env["account.account"].browse(v["account_id"]).code,
            ),
        )
        delivery = self._picking(self.picking_type_out, location, self.customer_location, 4.0)
        self.assertRecordValues(
            self._lines(delivery),
            sorted(
                [
                    {"account_id": self.account_dest.id, "debit": 400.0, "credit": 0.0, "quantity": 4.0},
                    {"account_id": account_goods.id, "debit": 0.0, "credit": 400.0, "quantity": -4.0},
                ],
                key=lambda v: self.env["account.account"].browse(v["account_id"]).code,
            ),
        )
