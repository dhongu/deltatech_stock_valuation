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
        cls.account_stock_input = cls.env["account.account"].create(
            {"name": "Stock Input Cat", "code": "SIC001", "account_type": "asset_current"}
        )
        cls.account_stock_output = cls.env["account.account"].create(
            {"name": "Stock Output Cat", "code": "SOC001", "account_type": "asset_current"}
        )

        # Categoria trebuie sa fie real_time pentru a genera NC
        cls.product_category.write(
            {
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                "property_stock_account_input_categ_id": cls.account_stock_input.id,
                "property_stock_account_output_categ_id": cls.account_stock_output.id,
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
        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.immediate.transfer":
            self.env[result["res_model"]].browse(result["res_id"]).process()

    def _get_nc_for_picking(self, picking):
        return self.env["account.move"].search([("stock_move_id", "in", picking.move_ids.ids)])

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
                "move_ids_without_package": [
                    Command.create(
                        {
                            "name": self.product.display_name,
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
                "move_ids_without_package": [
                    Command.create(
                        {
                            "name": self.product.display_name,
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
                "move_ids_without_package": [
                    Command.create(
                        {
                            "name": self.product.display_name,
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

    def test_04_equal_accounts_no_crash(self):
        """Cand acc_src == acc_dest in regula price_difference, _account_entry_move
        nu trebuie sa ridice exceptie si returneaza lista goala (nu genereaza NC inutila).

        Acesta testeaza direct bug-fix-ul din _account_entry_move: filtrarea corecta
        a valorilor False returnate de _prepare_account_move_vals.
        """
        # Regula price_difference cu conturi egale — simuleaza situatia in care
        # diferenta de pret nu necesita NC (e absorbita in acelasi cont)
        self.env["product.account.determination"].create(
            {
                "transaction_key": "price_difference",
                "valuation_class_id": self.valuation_class.id,
                "valuation_area_id": self.valuation_area.id,
                "company_id": self.env.company.id,
                "acc_src_id": self.account_valuation.id,
                "acc_dest_id": self.account_valuation.id,  # intentionat acelasi
                "acc_valuation_id": self.account_valuation.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": "Test price difference equal accounts",
                "product_id": self.product.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "product_uom_qty": 2.0,
                "product_uom": self.product.uom_id.id,
                "state": "done",
            }
        )
        svl = self.env["stock.valuation.layer"].create(
            {
                "stock_move_id": move.id,
                "value": 200.0,
                "unit_cost": 100.0,
                "quantity": 2.0,
                "company_id": self.env.company.id,
                "product_id": self.product.id,
            }
        )
        # qty=0 -> context price_difference=True -> regula gasita dar acc_src==acc_dest
        # -> _prepare_account_move_vals returneaza False
        # -> fix-ul [v for v in list if v] filtreaza corect -> returneaza []
        result = move._account_entry_move(0, "Test price diff", svl.id, 200.0)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [], "Lista trebuie sa fie goala cand acc_src == acc_dest")
