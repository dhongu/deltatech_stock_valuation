# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo.exceptions import UserError

from .test_common import TestCommon


class TestAccountMoveLine(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # compania default din test19 nu are plan de conturi complet — contul
        # de creanțe trebuie setat explicit pe partener
        cls.account_receivable = cls.env["account.account"].create(
            {
                "name": "Test Receivable",
                "code": "TREC01",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        cls.partner_a = cls.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "property_account_receivable_id": cls.account_receivable.id,
            }
        )
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Test Product A",
                "is_storable": True,
                "valuation_class_id": cls.valuation_class.id,
            }
        )

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Test Sale Journal",
                "code": "TSJ1",
                "type": "sale",
                "company_id": cls.env.company.id,
            }
        )
        # Create an account modifier

        cls.rule_receipt = cls.env["product.account.determination"].create(
            {
                "transaction_key": "stock_income",
                "valuation_class_id": cls.valuation_class.id,
                "valuation_area_id": cls.valuation_area.id,
                "company_id": cls.env.company.id,
                "acc_src_id": cls.account_src.id,
                "acc_dest_id": cls.account_dest.id,
                "acc_valuation_id": cls.account_valuation.id,
            }
        )

        cls.out_invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "date": "2017-01-01",
                "invoice_date": "2017-01-01",
                "partner_id": cls.partner_a.id,
                "currency_id": cls.env.company.currency_id.id,
                "journal_id": cls.sale_journal.id,
                "company_id": cls.env.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_a.id,
                            "product_uom_id": cls.product_a.uom_id.id,
                            "account_id": cls.account_src.id,
                            "price_unit": 23.98,
                            "quantity": 1.0,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )

        cls.account_move_line = cls.out_invoice.line_ids.filtered(lambda line: line.display_type == "product")

    def test_get_valuation_area_defined(self):
        """Test _get_valuation_area when valuation_area_id is explicitly defined."""
        valuation_area = self.account_move_line._get_valuation_area()
        self.assertEqual(
            valuation_area.id, self.valuation_area.id, "The valuation area should match the explicitly defined one."
        )

    def test_compute_account_id_with_valid_product(self):
        """
        Test _compute_account_id with a valid product that has a defined
        valuation class and valuation area.
        """
        self.account_move_line._compute_account_id()
        self.assertEqual(
            self.account_move_line.account_id,
            self.account_dest,
            "The account_id should match the source account defined in the rule.",
        )

    def test_get_valuation_area_inherited_from_company(self):
        """Test _get_valuation_area when valuation_area_id is inherited from the company."""
        self.account_move_line.valuation_area_id = False
        self.env.company.valuation_area_id = self.valuation_area

        valuation_area = self.account_move_line._get_valuation_area()
        self.assertEqual(
            valuation_area.id,
            self.valuation_area.id,
            "The valuation area should match the one inherited from the company.",
        )

    def test_get_valuation_area_undefined_raises_error(self):
        """Test _get_valuation_area raises UserError when no valuation area is defined."""
        self.account_move_line.valuation_area_id = False
        self.env.company.valuation_area_id = False

        with self.assertRaises(UserError):
            self.account_move_line._get_valuation_area()

    def test_compute_account_id_line_without_product(self):
        """O linie de factură fără produs păstrează contul și nu cade la calculul clasei de evaluare."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": "2017-01-01",
                "partner_id": self.partner_a.id,
                "journal_id": self.sale_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service without product",
                            "account_id": self.account_src.id,
                            "price_unit": 10.0,
                            "quantity": 1.0,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids
        self.assertFalse(line.product_id)
        line._compute_account_id()
        self.assertEqual(line.account_id, self.account_src)

    def _create_service_in_class_category(self):
        """Serviciu fără clasă proprie, într-o categorie cu clasă de evaluare."""
        self.account_service_income = self.env["account.account"].create(
            {"name": "Test Service Income", "code": "TSI704", "account_type": "income"}
        )
        category = self.env["product.category"].create(
            {
                "name": "Test Service Category",
                "valuation_class_id": self.valuation_class.id,
                "property_account_income_categ_id": self.account_service_income.id,
            }
        )
        return self.env["product.product"].create({"name": "Test Service", "type": "service", "categ_id": category.id})

    def _create_invoice(self, product):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": "2017-01-01",
                "partner_id": self.partner_a.id,
                "journal_id": self.sale_journal.id,
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "price_unit": 10.0, "quantity": 1.0, "tax_ids": []})
                ],
            }
        )

    def test_service_without_area_keeps_standard_account(self):
        """Firmă cu arii fără arie implicită: serviciul cu clasă din categorie nu oprește factura.

        Nu există regulă fără arie, deci linia primește contul de venit al categoriei.
        """
        self.env.company.write({"use_valuation_area": True, "valuation_area_id": False})
        service = self._create_service_in_class_category()
        self.assertEqual(service._get_valuation_class(), self.valuation_class)

        invoice = self._create_invoice(service)
        line = invoice.invoice_line_ids
        self.assertFalse(line.valuation_area_id)
        self.assertEqual(line.account_id, self.account_service_income)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_service_without_area_uses_rule_without_area(self):
        """Dacă există o regulă fără arie pentru clasa serviciului, factura o folosește."""
        self.env.company.write({"use_valuation_area": True, "valuation_area_id": False})
        service = self._create_service_in_class_category()
        account_704 = self.env["account.account"].create(
            {"name": "Test Rule Income 704", "code": "TRI704", "account_type": "income"}
        )
        self.env["product.account.determination"].create(
            {
                "transaction_key": "stock_income",
                "valuation_class_id": self.valuation_class.id,
                "valuation_area_id": False,
                "company_id": self.env.company.id,
                "acc_dest_id": account_704.id,
            }
        )

        invoice = self._create_invoice(service)
        self.assertEqual(invoice.invoice_line_ids.account_id, account_704)

    def test_storable_without_area_still_raises(self):
        """Produsul stocabil fără arie rămâne blocat: comportamentul lui nu se schimbă."""
        self.env.company.write({"use_valuation_area": True, "valuation_area_id": False})
        with self.assertRaises(UserError):
            self._create_invoice(self.product_a)
