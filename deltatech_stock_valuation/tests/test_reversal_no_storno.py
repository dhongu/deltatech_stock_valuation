# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class ReversalCommon(AccountTestInvoicingCommon):
    """Inversarea unei note de stoc trebuie să aducă evaluarea la zero, nu să dubleze
    cantitatea, cu și fără storno."""

    account_storno = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.valuation_area_level = "company"
        cls.env.company.account_storno = cls.account_storno
        cls.env.company.set_stock_valuation_at_company_level()
        cls.valuation_area = cls.env.company.valuation_area_id
        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation RV",
                "code": "SVRV1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        cls.counterpart_account = cls.company_data["default_account_expense"]
        cls.journal = cls.env["account.journal"].create({"name": "Misc RV", "type": "general", "code": "JVRV"})
        cls.product = cls.product_a
        cls.product.is_storable = True

    def _post_receipt(self, amount, quantity):
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
                            "debit": amount,
                            "product_id": self.product.id,
                            "product_uom_id": self.product.uom_id.id,
                            "quantity": quantity,
                            "valuation_area_id": self.valuation_area.id,
                        },
                    ),
                    (0, 0, {"name": "Counterpart", "account_id": self.counterpart_account.id, "credit": amount}),
                ],
            }
        )
        move.action_post()
        return move

    def _stock_line(self, move):
        return move.line_ids.filtered(lambda line: line.account_id == self.account_stock_val)

    def _history(self):
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


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestReversalNoStorno(ReversalCommon):
    """Fără storno, nucleul trece suma pe partea opusă și copiază cantitatea cu același
    semn; cantitatea trebuie inversată odată cu partea."""

    def test_reversal_without_storno_cancels_quantity(self):
        receipt = self._post_receipt(1000.0, 10.0)
        reversal = receipt._reverse_moves(cancel=True)
        line = self._stock_line(reversal)
        self.assertEqual(line.credit, 1000.0)
        # pe nota de stoc, cantitatea e semnată: negativă pe linia de credit
        self.assertEqual(line.quantity, -10.0)
        history = self._history()
        self.assertFalse(history.quantity_final, "inversarea trebuie să anuleze cantitatea, nu s-o dubleze")
        self.assertFalse(history.amount_final)

    def test_reversal_updates_current_valuation(self):
        """Recepție 5 buc, apoi inversarea ei: cantitatea e zero și în evaluarea
        curentă (product.valuation), nu doar în istoric."""
        receipt = self._post_receipt(500.0, 5.0)
        receipt._reverse_moves(cancel=True)
        self._history()
        self.env["product.valuation"]._recompute_all_amount()
        valuation = self.env["product.valuation"].search(
            [
                ("product_id", "=", self.product.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", self.env.company.id),
            ]
        )
        self.assertFalse(sum(valuation.mapped("quantity")))


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestReversalStorno(ReversalCommon):
    """Cu storno, linia inversată rămâne pe aceeași parte cu sumă negativă, iar semnul
    sumei anulează intrarea. O linie de valoare zero (mișcare la cost 0) nu are semn
    de sumă, deci cantitatea ei trebuie inversată."""

    account_storno = True

    def test_reversal_with_storno_cancels_quantity(self):
        receipt = self._post_receipt(1000.0, 10.0)
        reversal = receipt._reverse_moves(cancel=True)
        line = self._stock_line(reversal)
        self.assertEqual(line.debit, -1000.0)
        self.assertEqual(line.quantity, 10.0)
        history = self._history()
        self.assertFalse(history.quantity_final)
        self.assertFalse(history.amount_final)

    def test_zero_value_reversal_with_storno(self):
        receipt = self._post_receipt(0.0, 4.0)
        receipt._reverse_moves(cancel=True)
        history = self._history()
        self.assertFalse(history.quantity_final, "inversarea unei mișcări la cost 0 trebuie să anuleze cantitatea")
