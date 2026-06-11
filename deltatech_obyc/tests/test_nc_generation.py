# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import Command
from odoo.tests import tagged

from .test_common import TestCommon


@tagged("post_install", "-at_install")
class TestNCGeneration(TestCommon):
    """
    Teste de integrare end-to-end: la validarea unui picking se generează NC
    cu conturile din matricea OBYC, nu din categoria produsului.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Conturi pentru categoria produsului (necesare pentru real_time valuation)
        cls.account_stock_valuation = cls.env["account.account"].create(
            {"name": "Stock Valuation Cat", "code": "SVC001", "account_type": "asset_current"}
        )

        # Categoria trebuie sa fie real_time pentru a genera NC
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                "property_stock_journal": cls.stock_journal.id,
            }
        )
        cls.product.standard_price = 100.0

        # Reguli OBYC pentru tranzactiile testate (fara account_modifier)
        for key, src, dest in [
            ("stock_receipt", cls.account_src, cls.account_dest),
            ("stock_delivery", cls.account_dest, cls.account_src),
            ("return_to_supplier", cls.account_dest, cls.account_src),
            ("return_from_customer", cls.account_src, cls.account_dest),
        ]:
            cls.env["product.account.determination"].create(
                {
                    "transaction_key": key,
                    "valuation_class_id": cls.valuation_class.id,
                    "valuation_area_id": cls.valuation_area.id,
                    "company_id": cls.env.company.id,
                    "acc_src_id": src.id,
                    "acc_dest_id": dest.id,
                    "acc_valuation_id": cls.account_valuation.id,
                }
            )

        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

    def _validate_picking(self, picking):
        picking.action_confirm()
        picking.move_ids._set_quantity_done(picking.move_ids[0].product_uom_qty)
        # demo_mode sare validarea de transportator din l10n_ro_edi_stock (e-Transport)
        result = picking.with_context(demo_mode=True).button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.immediate.transfer":
            self.env[result["res_model"]].browse(result["res_id"]).process()

    def _get_nc_for_picking(self, picking):
        # în O19 legătura e stock_move.account_move_id (account.move nu are stock_move_id)
        return picking.move_ids.account_move_id

    def test_01_receipt_generates_nc_with_obyc_accounts(self):
        """Receptie furnizor → NC cu conturile din regula OBYC stock_receipt.

        Pentru receptie Odoo genereaza:
          - Debit:  acc_valuation (intrare in stoc)
          - Credit: acc_src      (cont intermediar furnizor / stock input)
        acc_dest este folosit doar la livrari si retururi.
        """
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        self._validate_picking(picking)

        nc_moves = self._get_nc_for_picking(picking)
        self.assertTrue(nc_moves, "Nu s-a generat nicio NC la receptia furnizor")
        self.assertTrue(all(m.state == "posted" for m in nc_moves), "NC nu este postata")

        all_accounts = nc_moves.line_ids.account_id
        # La receptie: debit acc_valuation, credit acc_src
        self.assertIn(self.account_src, all_accounts, "Contul sursa OBYC (credit) lipseste din NC")
        self.assertIn(self.account_valuation, all_accounts, "Contul de evaluare OBYC (debit) lipseste din NC")

        # Verifica sensul: acc_valuation apare pe debit, acc_src pe credit
        debit_accounts = nc_moves.line_ids.filtered(lambda l: l.debit > 0).account_id
        credit_accounts = nc_moves.line_ids.filtered(lambda l: l.credit > 0).account_id
        self.assertIn(self.account_valuation, debit_accounts, "acc_valuation trebuie sa fie pe debit la receptie")
        self.assertIn(self.account_src, credit_accounts, "acc_src trebuie sa fie pe credit la receptie")

    def test_02_delivery_generates_nc_with_obyc_accounts(self):
        """Livrare client → NC cu conturile din regula OBYC stock_delivery."""
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 10.0)

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                ],
            }
        )
        self._validate_picking(picking)

        nc_moves = self._get_nc_for_picking(picking)
        self.assertTrue(nc_moves, "Nu s-a generat nicio NC la livrarea clientului")
        self.assertTrue(all(m.state == "posted" for m in nc_moves), "NC nu este postata")

        all_accounts = nc_moves.line_ids.account_id
        self.assertIn(self.account_valuation, all_accounts, "Contul de evaluare OBYC lipseste din NC")

    def test_03_nc_carries_valuation_area(self):
        """Liniile NC trebuie sa aiba valuation_area_id setat."""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
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
        self._validate_picking(picking)

        nc_moves = self._get_nc_for_picking(picking)
        self.assertTrue(nc_moves)

        lines_with_product = nc_moves.line_ids.filtered(lambda l: l.product_id == self.product)
        for line in lines_with_product:
            self.assertEqual(
                line.valuation_area_id,
                self.valuation_area,
                f"Linia NC pentru contul {line.account_id.code} nu are valuation_area_id setat",
            )

    def _make_receipt(self, qty=10.0):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        self._validate_picking(picking)
        return picking

    def test_04_nc_uses_valuation_area_journal(self):
        """NC-ul mișcărilor OBYC trebuie generat pe jurnalul de stoc al ariei de
        evaluare, nu pe jurnalul de stoc al companiei."""
        area_journal = self.env["account.journal"].create(
            {"name": "Area Stock Journal", "code": "ASJ1", "type": "general"}
        )
        self.valuation_area.stock_journal_id = area_journal

        picking = self._make_receipt()
        nc_moves = self._get_nc_for_picking(picking)
        self.assertTrue(nc_moves, "Nu s-a generat NC la recepție")
        self.assertEqual(
            nc_moves.journal_id,
            area_journal,
            "NC-ul trebuie să folosească jurnalul ariei de evaluare",
        )

    def test_05_return_to_supplier_uses_storno(self):
        """Cu storno activ pe companie, returul la furnizor se înregistrează în roșu:
        aceleași conturi ca recepția (Dr valuation / Cr src), cu sume negative."""
        self.env.company.account_storno = True
        # regula de retur configurată simetric cu recepția: doar acc_dest setat
        # → nota "neagră" ar fi Dr acc_dest / Cr valuation; storno o inversează
        rule = self.env["product.account.determination"].search(
            [("transaction_key", "=", "return_to_supplier"), ("company_id", "=", self.env.company.id)]
        )
        rule.write({"acc_src_id": False, "acc_dest_id": self.account_src.id})

        picking = self._make_receipt()

        return_wizard = (
            self.env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking").create({})
        )
        return_wizard.product_return_moves.quantity = 5.0
        action = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(action["res_id"])
        self._validate_picking(return_picking)

        nc_return = self._get_nc_for_picking(return_picking)
        self.assertTrue(nc_return, "Nu s-a generat NC la retur")
        self.assertTrue(all(m.state == "posted" for m in nc_return), "NC-ul de retur nu este postat")

        valuation_line = nc_return.line_ids.filtered(lambda line: line.account_id == self.account_valuation)
        src_line = nc_return.line_ids.filtered(lambda line: line.account_id == self.account_src)
        self.assertTrue(valuation_line and src_line, "NC-ul de retur trebuie să aibă liniile pe conturile recepției")
        # storno (roșu): valoarea pe partea tranzacției originale, cu semn negativ
        self.assertEqual(valuation_line.debit, -500.0, "valuation trebuie debitat cu sumă negativă (storno)")
        self.assertEqual(valuation_line.credit, 0.0)
        self.assertEqual(src_line.credit, -500.0, "contul sursă trebuie creditat cu sumă negativă (storno)")
        self.assertEqual(src_line.debit, 0.0)
