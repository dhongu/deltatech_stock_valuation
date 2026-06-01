# ©  2024 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons rcoot folder for license details

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestStockValuation(AccountTestInvoicingCommon):
    """
    Testări generale pentru evaluarea stocului prin documente contabile.
    Verifică impactul diferitelor tipuri de facturi (ieșire, retur, intrare)
    asupra conturilor de evaluare.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.account = cls.env["account.account"].create(
            {
                "name": "Account A",
                "code": "1234",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "type": "sale",
                "code": "TEST",
            }
        )

        # Enable valuation areas so move lines on stock valuation accounts are processed.
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _default_date(self):
        return fields.Date.from_string(fields.Date.today()) + relativedelta(day=1, days=15)

    def _post_move(self, move_type, product, qty, price, date=None, account=None):
        """Create and post an invoice/refund with a single line on the stock valuation account."""
        account = account or self.account
        date = date or self._default_date()
        tax_field = "default_tax_purchase" if move_type in ("in_invoice", "in_refund") else "default_tax_sale"
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "invoice_date": date,
                "date": date,
                "partner_id": self.partner_b.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "account_id": account.id,
                            "quantity": qty,
                            "price_unit": price,
                            "tax_ids": [Command.set(self.company_data[tax_field].ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def _new_product(self, name="Storable Product"):
        return self.env["product.product"].create(
            {
                "name": name,
                "is_storable": True,
                "standard_price": 0.0,
            }
        )

    def _get_valuation(self, product, account=None):
        account = account or self.account
        return (
            self.env["product.valuation"]
            .with_context(active_test=False)
            .search(
                [
                    ("product_id", "=", product.id),
                    ("valuation_area_id", "=", self.valuation_area.id),
                    ("account_id", "=", account.id),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
        )

    def _get_history(self, product, month, account=None):
        account = account or self.account
        return self.env["product.valuation.history"].search(
            [
                ("product_id", "=", product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", account.id),
                ("company_id", "=", self.env.company.id),
                ("month", "=", month),
            ],
            limit=1,
        )

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------
    def test_new_product_receipt_creates_product_valuation(self):
        """
        Verifică faptul că la adăugarea unui produs nou și înregistrarea unei
        recepții cu factură (vendor bill pe contul de evaluare a stocului),
        după postare se creează o linie nouă în `product.valuation`.
        """
        # Activăm aria de evaluare la nivel de companie, astfel încât liniile
        # contabile să primească o valuation_area și să fie procesate.
        self.env.company.use_valuation_area = True
        self.env.company.set_stock_valuation_at_company_level()
        valuation_area = self.env.company.valuation_area_id
        self.assertTrue(valuation_area, "Valuation area should be configured at company level")

        # Produs nou, inexistent până acum în baza de date.
        new_product = self.env["product.product"].create(
            {
                "name": "New Storable Product",
                "is_storable": True,
                "standard_price": 0.0,
            }
        )

        # Nu trebuie să existe nicio evaluare pentru produsul nou.
        PV = self.env["product.valuation"]
        domain = [
            ("product_id", "=", new_product.id),
            ("valuation_area_id", "=", valuation_area.id),
            ("account_id", "=", self.account.id),
            ("company_id", "=", self.env.company.id),
        ]
        self.assertFalse(
            PV.with_context(active_test=False).search(domain),
            "No product.valuation should exist for a brand new product",
        )

        # Recepție cu factură: vendor bill pe contul de evaluare a stocului.
        today = fields.Date.from_string(fields.Date.today())
        date = today + relativedelta(day=1, days=15)
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": date,
                "date": date,
                "partner_id": self.partner_b.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": new_product.id,
                            "account_id": self.account.id,
                            "quantity": 10.0,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(self.company_data["default_tax_purchase"].ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()

        # După postare trebuie să existe o linie nouă în product.valuation.
        valuation = PV.search(domain, limit=1)
        self.assertTrue(
            valuation,
            "A new product.valuation line should be created after posting the receipt invoice",
        )
        self.assertEqual(valuation.quantity, 10.0, "Quantity should reflect the received quantity")
        self.assertEqual(valuation.amount, 500.0, "Amount should reflect the received value")
        self.assertEqual(valuation.price, 50.0, "Unit price should be amount / quantity")

        # De asemenea, trebuie să existe o linie în istoricul lunar (product.valuation.history)
        # pentru luna recepției.
        PVH = self.env["product.valuation.history"]
        history = PVH.search(
            [
                ("product_id", "=", new_product.id),
                ("valuation_area_id", "=", valuation_area.id),
                ("account_id", "=", self.account.id),
                ("company_id", "=", self.env.company.id),
                ("month", "=", date.strftime("%Y%m")),
            ],
            limit=1,
        )
        self.assertTrue(
            history,
            "A product.valuation.history line should be created for the receipt month",
        )
        self.assertEqual(history.quantity_in, 10.0, "Monthly quantity in should reflect the received quantity")
        self.assertEqual(history.debit, 500.0, "Monthly debit should reflect the received value")
        self.assertEqual(history.quantity, 10.0, "Monthly net quantity should be positive for a receipt")
        self.assertEqual(history.amount, 500.0, "Monthly net amount should be debit - credit")
        self.assertEqual(history.quantity_final, 10.0, "Final quantity should match the current valuation")
        self.assertEqual(history.amount_final, 500.0, "Final amount should match the current valuation")

    def test_purchase_refund_reduces_valuation(self):
        """
        Scenariu retur la furnizor: o recepție urmată de un retur (in_refund)
        trebuie să scadă cantitatea și valoarea atât în `product.valuation`,
        cât și în istoricul lunar.
        """
        product = self._new_product("Refund Product")
        date = self._default_date()

        # Recepție 10 buc @ 50 = 500
        self._post_move("in_invoice", product, qty=10.0, price=50.0, date=date)
        # Retur 4 buc @ 50 = 200
        self._post_move("in_refund", product, qty=4.0, price=50.0, date=date)

        valuation = self._get_valuation(product)
        self.assertTrue(valuation, "product.valuation should exist after receipt and refund")
        self.assertEqual(valuation.quantity, 6.0, "Returned quantity should be subtracted")
        self.assertEqual(valuation.amount, 300.0, "Returned value should be subtracted")
        self.assertEqual(valuation.price, 50.0, "Average price stays the same for same-price refund")

        history = self._get_history(product, date.strftime("%Y%m"))
        self.assertEqual(history.quantity_in, 6.0, "Net quantity in = received - returned")
        self.assertEqual(history.debit, 500.0, "Debit comes from the receipt")
        self.assertEqual(history.credit, 200.0, "Credit comes from the refund")
        self.assertEqual(history.quantity, 6.0, "Net monthly quantity")
        self.assertEqual(history.amount, 300.0, "Net monthly amount = debit - credit")
        self.assertEqual(history.quantity_final, 6.0)
        self.assertEqual(history.amount_final, 300.0)

    def test_sale_invoice_reduces_valuation(self):
        """
        Scenariu ieșire din stoc: o recepție urmată de o factură de client
        (out_invoice) pe contul de evaluare trebuie să scadă cantitatea și valoarea.
        Ieșirea este valorizată la cost (cost mediu ponderat).
        """
        product = self._new_product("Sold Product")
        date = self._default_date()

        # Recepție 10 buc @ 50 = 500
        self._post_move("in_invoice", product, qty=10.0, price=50.0, date=date)
        # Ieșire 3 buc la cost 50 = 150
        self._post_move("out_invoice", product, qty=3.0, price=50.0, date=date)

        valuation = self._get_valuation(product)
        self.assertEqual(valuation.quantity, 7.0, "Stock decreases by the sold quantity")
        self.assertEqual(valuation.amount, 350.0, "Value decreases by the cost of goods sold")
        self.assertEqual(valuation.price, 50.0, "Average price is unchanged when issuing at cost")

        history = self._get_history(product, date.strftime("%Y%m"))
        self.assertEqual(history.quantity_in, 10.0)
        self.assertEqual(history.quantity_out, 3.0, "Sold quantity is tracked as outgoing")
        self.assertEqual(history.quantity, 7.0, "Net monthly quantity = in - out")
        self.assertEqual(history.amount, 350.0)
        self.assertEqual(history.quantity_final, 7.0)
        self.assertEqual(history.amount_final, 350.0)

    def test_customer_refund_increases_valuation(self):
        """
        Scenariu retur de la client (out_refund): mărfurile revin în stoc,
        deci cantitatea și valoarea cresc.
        """
        product = self._new_product("Customer Refund Product")
        date = self._default_date()

        # Recepție 10 buc @ 50 = 500, apoi ieșire 4 buc @ 50 = 200
        self._post_move("in_invoice", product, qty=10.0, price=50.0, date=date)
        self._post_move("out_invoice", product, qty=4.0, price=50.0, date=date)
        # Retur de la client 1 buc @ 50 = 50 (revine în stoc)
        self._post_move("out_refund", product, qty=1.0, price=50.0, date=date)

        valuation = self._get_valuation(product)
        self.assertEqual(valuation.quantity, 7.0, "Customer return adds the quantity back")
        self.assertEqual(valuation.amount, 350.0)

        history = self._get_history(product, date.strftime("%Y%m"))
        self.assertEqual(history.quantity_out, 3.0, "Customer return reduces the net outgoing quantity")
        self.assertEqual(history.quantity, 7.0)

    def test_average_cost_two_receipts(self):
        """
        Cost mediu ponderat (AVCO): două recepții la prețuri diferite trebuie să
        producă un preț mediu corect în `product.valuation`.
        """
        product = self._new_product("AVCO Product")
        date = self._default_date()

        # 10 @ 50 = 500 și 10 @ 70 = 700 -> 20 buc, 1200, preț mediu 60
        self._post_move("in_invoice", product, qty=10.0, price=50.0, date=date)
        self._post_move("in_invoice", product, qty=10.0, price=70.0, date=date)

        valuation = self._get_valuation(product)
        self.assertEqual(valuation.quantity, 20.0)
        self.assertEqual(valuation.amount, 1200.0)
        self.assertEqual(valuation.price, 60.0, "Weighted average price = total amount / total quantity")

    def test_history_propagation_across_months(self):
        """
        Recepții în luni diferite: istoricul lunar trebuie să propage corect
        soldul final al unei luni ca sold inițial al lunii următoare.
        """
        product = self._new_product("Multi Month Product")
        today = fields.Date.from_string(fields.Date.today())
        prev_date = today + relativedelta(day=1, months=-1, days=10)
        cur_date = today + relativedelta(day=1, days=10)

        # Luna anterioară: 10 @ 50, luna curentă: 5 @ 60
        self._post_move("in_invoice", product, qty=10.0, price=50.0, date=prev_date)
        self._post_move("in_invoice", product, qty=5.0, price=60.0, date=cur_date)

        h_prev = self._get_history(product, prev_date.strftime("%Y%m"))
        h_cur = self._get_history(product, cur_date.strftime("%Y%m"))

        self.assertEqual(h_prev.quantity_final, 10.0)
        self.assertEqual(h_prev.amount_final, 500.0)
        # Soldul final al lunii anterioare devine sold inițial al lunii curente
        self.assertEqual(h_cur.quantity_initial, 10.0)
        self.assertEqual(h_cur.amount_initial, 500.0)
        self.assertEqual(h_cur.quantity_final, 15.0)
        self.assertEqual(h_cur.amount_final, 800.0)

        # Evaluarea curentă reflectă ultima lună
        valuation = self._get_valuation(product)
        self.assertEqual(valuation.quantity, 15.0)
        self.assertEqual(valuation.amount, 800.0)

    def test_get_valuation_creates_records(self):
        """
        `get_valuation` trebuie să creeze o înregistrare nouă (cu valori 0) atunci
        când nu există, atât pentru `product.valuation`, cât și pentru istoric.
        """
        product = self._new_product("Get Valuation Product")

        pv = self.env["product.valuation"].get_valuation(
            product.id, self.valuation_area.id, self.account.id, self.env.company.id
        )
        self.assertTrue(pv.id, "A product.valuation record should be created")
        self.assertEqual(pv.quantity, 0.0)
        self.assertEqual(pv.amount, 0.0)

        # Al doilea apel returnează aceeași înregistrare, nu una nouă
        pv2 = self.env["product.valuation"].get_valuation(
            product.id, self.valuation_area.id, self.account.id, self.env.company.id
        )
        self.assertEqual(pv, pv2, "get_valuation should be idempotent")

        date = self._default_date()
        pvh = self.env["product.valuation.history"].get_valuation(
            product.id, self.valuation_area.id, self.account.id, date, self.env.company.id
        )
        self.assertTrue(pvh.id, "A product.valuation.history record should be created")
        self.assertEqual(pvh.month, date.strftime("%Y%m"))
        self.assertEqual(pvh.quantity_initial, 0.0)

    def test_non_storable_product_skips_valuation_area(self):
        """
        Un produs ne-stocabil pe un cont de evaluare nu trebuie să primească arie
        de evaluare obligatorie și nici să fie blocat de constrângere.
        """
        consu_product = self.env["product.product"].create({"name": "Service-like", "is_storable": False})
        # Postarea nu trebuie să ridice eroare deși contul este de evaluare stoc.
        move = self._post_move("in_invoice", consu_product, qty=2.0, price=10.0)
        self.assertEqual(move.state, "posted")

    def test_account_move(self):
        """
        Verifică procesarea mai multor tipuri de mișcări contabile.
        Creează facturi de client, facturi de furnizor și retururi, le postează
        și validează indirect fluxul de date care va fi folosit pentru evaluare.
        """
        today = fields.Date.today()
        today = fields.Date.from_string(today)
        date = today + relativedelta(day=1, months=-1, days=15)

        invoices = self.env["account.move"].create(
            [
                {
                    "move_type": "out_invoice",
                    "invoice_date": date,
                    "date": date,
                    "partner_id": self.partner_a.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_a.id,
                                "account_id": self.account.id,
                                "quantity": 5.0,
                                "price_unit": 1000.0,
                                "tax_ids": [Command.set(self.company_data["default_tax_sale"].ids)],
                            }
                        )
                    ],
                },
                {
                    "move_type": "out_invoice",
                    "invoice_date": date,
                    "date": date,
                    "partner_id": self.company_data["company"].partner_id.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_a.id,
                                "account_id": self.account.id,
                                "quantity": 2.0,
                                "price_unit": 1500.0,
                                "tax_ids": [Command.set(self.company_data["default_tax_sale"].ids)],
                            }
                        )
                    ],
                },
                {
                    "move_type": "out_refund",
                    "invoice_date": date,
                    "date": date,
                    "partner_id": self.partner_a.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_a.id,
                                "account_id": self.account.id,
                                "quantity": 3.0,
                                "price_unit": 1000.0,
                                "tax_ids": [Command.set(self.company_data["default_tax_sale"].ids)],
                            }
                        )
                    ],
                },
                {
                    "move_type": "in_invoice",
                    "invoice_date": date,
                    "date": date,
                    "partner_id": self.partner_b.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_b.id,
                                "account_id": self.account.id,
                                "quantity": 10.0,
                                "price_unit": 800.0,
                                "tax_ids": [Command.set(self.company_data["default_tax_purchase"].ids)],
                            }
                        )
                    ],
                },
            ]
        )
        invoices.action_post()
