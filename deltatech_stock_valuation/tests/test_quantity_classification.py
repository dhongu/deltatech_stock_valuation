# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestQuantityClassification(AccountTestInvoicingCommon):
    """
    Testări pentru clasificarea cantităților (intrări/ieșiri/net) din notele contabile
    de tip `entry`, inclusiv storno (debit/credit negativ), și pentru constrângerile
    de unicitate și protecția prețului la cantități reziduale.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.valuation_area_level = "company"
        # storno (debit/credit negativ) — altfel postarea convertește debit negativ în credit
        cls.env.company.account_storno = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id

        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation QC",
                "code": "SVQC1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        cls.counterpart_account = cls.company_data["default_account_expense"]
        cls.journal = cls.env["account.journal"].create({"name": "Misc QC", "type": "general", "code": "JVQC"})

        cls.product = cls.product_a
        cls.product.is_storable = True

    def _post_entry(self, debit=0.0, credit=0.0, quantity=0.0):
        """Postează o notă contabilă de tip entry cu o linie pe contul de stoc
        (cu produs și cantitate) și contrapartidă fără produs. Suportă valori
        negative pe debit/credit (storno)."""
        move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
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
                            "quantity": quantity,
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
        move.action_post()
        self.env.cr.execute(
            "UPDATE account_move_line SET valuation_area_id = %s WHERE move_id = %s AND product_id IS NOT NULL",
            (self.valuation_area.id, move.id),
        )
        move.line_ids.invalidate_recordset(["valuation_area_id"])
        return move

    def _get_history(self):
        self.env["product.valuation.history"]._recompute_all_amount()
        return self.env["product.valuation.history"].search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            order="month desc",
            limit=1,
        )

    def test_entry_in_and_out(self):
        """Recepție (debit) + descărcare (credit) prin note entry:
        intrările și ieșirile trebuie clasificate corect, iar netul = in - out."""
        self._post_entry(debit=1000.0, quantity=10.0)
        self._post_entry(credit=300.0, quantity=3.0)

        history = self._get_history()
        self.assertTrue(history)
        self.assertEqual(history.quantity_in, 10.0)
        self.assertEqual(history.quantity_out, 3.0)
        self.assertEqual(history.quantity, 7.0)
        self.assertEqual(history.amount, 700.0)
        self.assertEqual(history.quantity_final, 7.0)
        self.assertEqual(history.amount_final, 700.0)

    def test_storno_entry(self):
        """Storno RO (debit negativ, cantitate pozitivă pe linie) trebuie să anuleze
        intrarea inițială atât valoric cât și cantitativ — storno parțial: rămân 6 buc."""
        self._post_entry(debit=1000.0, quantity=10.0)
        self._post_entry(debit=-400.0, quantity=4.0)

        history = self._get_history()
        self.assertTrue(history)
        self.assertEqual(history.quantity_in, 6.0)
        self.assertEqual(history.quantity_out, 0.0)
        self.assertEqual(history.quantity_final, 6.0)
        self.assertEqual(history.amount_final, 600.0)

    def test_storno_full_reversal_leaves_no_balance(self):
        """Storno total: combinația netează la zero, iar pasul 6 al recalculării
        șterge rândul gol din istoric."""
        self._post_entry(debit=1000.0, quantity=10.0)
        self._post_entry(debit=-1000.0, quantity=10.0)

        history = self._get_history()
        self.assertFalse(history, "rândul complet stornat trebuie eliminat din istoric")

    def test_current_valuation_matches_history(self):
        """product.valuation (agregarea fără lună) trebuie să dea aceleași cantități
        ca istoricul — cele două query-uri folosesc același helper de clasificare."""
        self._post_entry(debit=1000.0, quantity=10.0)
        self._post_entry(credit=300.0, quantity=3.0)

        history = self._get_history()
        self.env["product.valuation"]._recompute_all_amount()
        valuation = self.env["product.valuation"].search(
            [
                ("product_id", "=", self.product.id),
                ("valuation_area_id", "=", self.valuation_area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(valuation)
        self.assertEqual(valuation.quantity, history.quantity_final)
        self.assertEqual(valuation.amount, history.amount_final)
        self.assertAlmostEqual(valuation.price, 100.0, places=4)

    def test_unique_constraints(self):
        """Constrângerile de unicitate (models.Constraint) trebuie să fie active —
        în Odoo 19 lista _sql_constraints e ignorată silențios."""
        PV = self.env["product.valuation"]
        PV.get_valuation(self.product.id, self.valuation_area.id, self.account_stock_val.id, self.env.company.id)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            PV.create(
                {
                    "product_id": self.product.id,
                    "valuation_area_id": self.valuation_area.id,
                    "account_id": self.account_stock_val.id,
                    "company_id": self.env.company.id,
                }
            )
            PV.flush_model()

        PVH = self.env["product.valuation.history"]
        history = self._get_history()
        if not history:
            self._post_entry(debit=100.0, quantity=1.0)
            history = self._get_history()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            PVH.create(
                {
                    "product_id": history.product_id.id,
                    "valuation_area_id": history.valuation_area_id.id,
                    "account_id": history.account_id.id,
                    "company_id": history.company_id.id,
                    "month": history.month,
                }
            )
            PVH.flush_model()

    def test_history_allows_multiple_months(self):
        """Constrângerea moștenită din product.valuation trebuie suprascrisă pe istoric:
        aceeași combinație în luni diferite e validă."""
        PVH = self.env["product.valuation.history"]
        common = {
            "product_id": self.product.id,
            "valuation_area_id": self.valuation_area.id,
            "account_id": self.account_stock_val.id,
            "company_id": self.env.company.id,
        }
        PVH.create(dict(common, month="202601"))
        PVH.create(dict(common, month="202602"))
        PVH.flush_model()

    def test_residual_quantity_keeps_price(self):
        """O ajustare pur valorică (amount fără cantitate — ex. nota de corecție CMP
        periodic) nu trebuie să producă un preț aberant — se păstrează prețul anterior."""
        PV = self.env["product.valuation"]
        valuation = PV.get_valuation(
            self.product.id, self.valuation_area.id, self.account_stock_val.id, self.env.company.id
        )
        valuation.price = 100.0

        history = self.env["product.valuation.history"].create(
            {
                "product_id": self.product.id,
                "valuation_area_id": self.valuation_area.id,
                "account_id": self.account_stock_val.id,
                "company_id": self.env.company.id,
                "month": "202601",
                "quantity": 0.0,
                "amount": 5.0,
            }
        )
        self.assertEqual(history.quantity_final, 0.0)
        self.assertEqual(history.amount_final, 5.0)

        valuation._recompute_amount()
        self.assertEqual(valuation.price, 100.0, "prețul nu trebuie recalculat pe o cantitate reziduală/zero")
