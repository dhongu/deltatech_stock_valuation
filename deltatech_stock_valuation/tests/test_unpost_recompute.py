# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestUnpostRecompute(AccountTestInvoicingCommon):
    """
    Testări pentru recalcularea incrementală a evaluării: postare, de-postare
    (înapoi în draft), schimbarea datei contabile și izolarea multi-company.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.valuation_area_level = "company"
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation UR",
                "code": "SVUR1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        cls.counterpart_account = cls.company_data["default_account_expense"]
        cls.journal = cls.env["account.journal"].create({"name": "Misc UR", "type": "general", "code": "JVUR"})

        cls.product = cls.product_a
        cls.product.is_storable = True

    def _create_entry(self, debit=0.0, credit=0.0, quantity=0.0, date=None):
        # convenția semnată: cantitate pozitivă pe linia de debit, negativă pe credit
        signed_quantity = quantity if debit else -quantity
        return self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "date": date or fields.Date.today(),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Stock line",
                            "account_id": self.account_stock_val.id,
                            "debit": debit,
                            "credit": credit,
                            "product_id": self.product.id,
                            "product_uom_id": self.product.uom_id.id,
                            "quantity": signed_quantity,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Counterpart",
                            "account_id": self.counterpart_account.id,
                            "debit": credit,
                            "credit": debit,
                        },
                    ),
                ],
            }
        )

    def _history(self, month):
        return self.env["product.valuation.history"].search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
                ("month", "=", month),
            ],
            limit=1,
        )

    def _valuation(self):
        return self.env["product.valuation"].search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

    def test_post_incremental_updates_history(self):
        """Postarea trebuie să actualizeze incremental istoricul lunii (inclusiv
        soldurile finale — _compute_final trebuie să ruleze efectiv) și evaluarea curentă."""
        move = self._create_entry(debit=1000.0, quantity=10.0)
        move.action_post()

        month = move.date.strftime("%Y%m")
        history = self._history(month)
        self.assertTrue(history)
        self.assertEqual(history.quantity, 10.0)
        self.assertEqual(history.amount, 1000.0)
        self.assertEqual(history.quantity_final, 10.0, "soldul final trebuie recalculat la postare")
        self.assertEqual(history.amount_final, 1000.0)

        valuation = self._valuation()
        self.assertTrue(valuation)
        self.assertEqual(valuation.quantity, 10.0)
        self.assertEqual(valuation.amount, 1000.0)
        self.assertAlmostEqual(valuation.price, 100.0, places=4)

    def test_unpost_resets_valuation(self):
        """Trecerea înapoi în draft trebuie să anuleze efectul notei asupra evaluării."""
        move = self._create_entry(debit=1000.0, quantity=10.0)
        move.action_post()
        month = move.date.strftime("%Y%m")
        self.assertEqual(self._history(month).quantity_final, 10.0)

        move.button_draft()

        history = self._history(month)
        self.assertTrue(history)
        self.assertEqual(history.quantity, 0.0, "mișcarea lunii trebuie zerorizată după de-postare")
        self.assertEqual(history.amount, 0.0)
        self.assertEqual(history.quantity_final, 0.0)
        self.assertEqual(history.amount_final, 0.0)

        valuation = self._valuation()
        self.assertEqual(valuation.quantity, 0.0)
        self.assertEqual(valuation.amount, 0.0)

    def test_change_date_recomputes_both_months(self):
        """Mutarea notei în altă lună trebuie să recalculeze și luna veche, și luna nouă."""
        date_new = fields.Date.today().replace(day=15)
        date_old = (date_new.replace(day=1) - relativedelta(months=1)).replace(day=15)
        month_new = date_new.strftime("%Y%m")
        month_old = date_old.strftime("%Y%m")

        move = self._create_entry(debit=1000.0, quantity=10.0, date=date_old)
        move.action_post()
        self.assertEqual(self._history(month_old).quantity_final, 10.0)

        # mutare în luna curentă prin ciclul draft -> dată nouă -> repostare
        move.button_draft()
        move.name = False  # secvența jurnalului trebuie realiniată cu noua lună
        move.date = date_new
        move.action_post()

        history_old = self._history(month_old)
        self.assertEqual(history_old.quantity, 0.0, "luna veche trebuie zerorizată")
        self.assertEqual(history_old.quantity_final, 0.0)

        history_new = self._history(month_new)
        self.assertTrue(history_new)
        self.assertEqual(history_new.quantity, 10.0)
        self.assertEqual(history_new.quantity_final, 10.0)

        valuation = self._valuation()
        self.assertEqual(valuation.quantity, 10.0)
        self.assertEqual(valuation.amount, 1000.0)

    def test_backdated_entry_propagates_to_later_months(self):
        """O notă postată retroactiv trebuie să propage soldurile în toate lunile
        următoare (propagarea SQL cu window function, nu cascada lună-cu-lună)."""
        date_now = fields.Date.today().replace(day=15)
        date_old = (date_now.replace(day=1) - relativedelta(months=2)).replace(day=15)
        month_now = date_now.strftime("%Y%m")
        month_old = date_old.strftime("%Y%m")

        self._create_entry(debit=1000.0, quantity=10.0, date=date_old).action_post()
        self._create_entry(debit=500.0, quantity=5.0, date=date_now).action_post()

        history_now = self._history(month_now)
        self.assertEqual(history_now.quantity_initial, 10.0)
        self.assertEqual(history_now.quantity_final, 15.0)
        self.assertEqual(history_now.amount_final, 1500.0)

        # corecție retroactivă: încă 2 buc / 200 în luna veche
        self._create_entry(debit=200.0, quantity=2.0, date=date_old).action_post()

        history_old = self._history(month_old)
        self.assertEqual(history_old.quantity, 12.0)
        self.assertEqual(history_old.quantity_final, 12.0)
        self.assertEqual(history_old.amount_final, 1200.0)

        history_now = self._history(month_now)
        self.assertEqual(history_now.quantity_initial, 12.0, "soldul inițial al lunii curente trebuie propagat")
        self.assertEqual(history_now.amount_initial, 1200.0)
        self.assertEqual(history_now.quantity_final, 17.0)
        self.assertEqual(history_now.amount_final, 1700.0)

        valuation = self._valuation()
        self.assertEqual(valuation.quantity, 17.0)
        self.assertEqual(valuation.amount, 1700.0)
        self.assertAlmostEqual(valuation.price, 100.0, places=4)

    def test_value_only_adjustment_updates_price(self):
        """O notă de corecție pur valorică (fără cantitate — pattern-ul
        l10n_ro_stock_cmp_periodic) trebuie absorbită în valoare și reflectată
        în preț atâta timp cât există cantitate în stoc."""
        self._create_entry(debit=1000.0, quantity=10.0).action_post()
        # corecție valorică: +50 lei, cantitate zero
        self._create_entry(debit=50.0, quantity=0.0).action_post()

        month = fields.Date.today().strftime("%Y%m")
        history = self._history(month)
        self.assertEqual(history.quantity_final, 10.0)
        self.assertEqual(history.amount_final, 1050.0)

        valuation = self._valuation()
        self.assertEqual(valuation.quantity, 10.0)
        self.assertEqual(valuation.amount, 1050.0)
        self.assertAlmostEqual(valuation.price, 105.0, places=4)

    def test_multicompany_refresh_keeps_other_company(self):
        """Recalcularea completă a evaluării pe compania curentă nu trebuie să șteargă
        evaluările altei companii care folosește aceleași conturi."""
        company_b = self.env["res.company"].create({"name": "Other Co UR"})
        area_b = self.env["valuation.area"].create({"name": "Area B", "code": "AREAB", "company_id": company_b.id})
        valuation_b = self.env["product.valuation"].create(
            {
                "product_id": self.product.id,
                "valuation_area_id": area_b.id,
                "account_id": self.account_stock_val.id,
                "company_id": company_b.id,
                "quantity": 5.0,
                "amount": 500.0,
                "price": 100.0,
            }
        )

        # refresh complet pe compania curentă (A)
        self.env["product.valuation"]._recompute_all_amount()

        self.assertTrue(valuation_b.exists(), "evaluarea companiei B nu trebuie ștearsă de refresh-ul companiei A")
        self.assertEqual(valuation_b.quantity, 5.0)
        self.assertEqual(valuation_b.amount, 500.0)
