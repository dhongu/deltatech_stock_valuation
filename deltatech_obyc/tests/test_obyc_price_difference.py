# © 2026 Deltatech
# See README.rst file on addons root folder for license details
#
# OBYC-014: factura furnizorului cu diferență de preț sau de curs corectează stocul și
# închide contul de recepții nefacturate (408).

from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .test_obyc_entries import TestObycEntries


@tagged("post_install", "-at_install")
class TestObycPriceDifference(TestObycEntries):
    # fixturile vin din TestObycEntries; testele lui nu se rulează a doua oară
    for _name in dir(TestObycEntries):
        if _name.startswith("test"):
            locals()[_name] = None
    del _name

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_fx_loss = cls.env["account.account"].create(
            {"name": "Test FX Loss", "code": "TFXL01", "account_type": "expense"}
        )
        cls.account_fx_gain = cls.env["account.account"].create(
            {"name": "Test FX Gain", "code": "TFXG01", "account_type": "income_other"}
        )
        cls.env.company.write(
            {
                "expense_currency_exchange_account_id": cls.account_fx_loss.id,
                "income_currency_exchange_account_id": cls.account_fx_gain.id,
            }
        )

    def _purchase(self, qty, price, currency=None):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "currency_id": (currency or self.env.company.currency_id).id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "price_unit": price,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    def _receive(self, order):
        picking = order.picking_ids
        picking.move_ids._set_quantity_done(picking.move_ids[0].product_uom_qty)
        picking.with_context(demo_mode=True).button_validate()
        return picking

    def _bill(self, order, price, qty=None, invoice_date=None):
        order.action_create_invoice()
        bill = order.invoice_ids.filtered(lambda m: m.state == "draft")[:1]
        bill.invoice_date = invoice_date or fields.Date.today()
        bill.journal_id = self.purchase_journal
        if qty is not None:
            bill.invoice_line_ids.quantity = qty
        bill.invoice_line_ids.price_unit = price
        return bill

    def _balance(self, account):
        lines = self.env["account.move.line"].search([("account_id", "=", account.id), ("parent_state", "=", "posted")])
        return sum(lines.mapped("balance"))

    def test_price_up_goods_in_stock(self):
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        bill = self._bill(order, 110.0)
        bill.action_post()
        self.assertEqual(self._balance(self.account_src), 0.0, "408 se închide")
        self.assertEqual(self._balance(self.account_valuation), 1100.0)
        receipt = order.picking_ids.move_ids
        self.assertEqual(receipt.value, 1100.0)
        self.assertEqual(self.product.standard_price, 110.0)
        # linia produsului stinge 408 la prețul facturii, corecția aduce stocul la 1100
        self.assertEqual(
            sum(bill.line_ids.filtered(lambda aml: aml.account_id == self.account_valuation).mapped("balance")), 100.0
        )

    def test_price_down_goods_in_stock(self):
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        self._bill(order, 90.0).action_post()
        self.assertEqual(self._balance(self.account_src), 0.0)
        self.assertEqual(self._balance(self.account_valuation), 900.0)
        self.assertEqual(self.product.standard_price, 90.0)

    def test_price_difference_after_partial_delivery(self):
        """6 din 10 bucăți au ieșit la 100: din +100, 60 merg pe cheltuiala livrării."""
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        self._delivery(6.0)
        self.assertEqual(self._balance(self.account_dest), 600.0)
        self._bill(order, 110.0).action_post()
        self.assertEqual(self._balance(self.account_src), 0.0)
        self.assertEqual(self._balance(self.account_valuation), 440.0, "4 buc × 110")
        self.assertEqual(self._balance(self.account_dest), 660.0)
        self.assertEqual(self.product.standard_price, 110.0)

    def test_price_difference_uses_dedicated_rule(self):
        account = self.env["account.account"].create(
            {"name": "Test Dedicated 408", "code": "TDED01", "account_type": "asset_current"}
        )
        self.env["product.account.determination"].create(
            {
                "transaction_key": "stock_receipt_price_difference",
                "valuation_class_id": self.valuation_class.id,
                "valuation_area_id": self.valuation_area.id,
                "company_id": self.env.company.id,
                "acc_src_id": account.id,
                "acc_valuation_id": self.account_valuation.id,
            }
        )
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        self._bill(order, 110.0).action_post()
        self.assertEqual(self._balance(account), -100.0)
        self.assertEqual(self._balance(self.account_src), 100.0, "rămâne doar diferența, pe contul dedicat")

    def test_bill_before_receipt_has_no_correction(self):
        order = self._purchase(10.0, 100.0)
        bill = self._bill(order, 110.0, qty=10.0)
        bill.action_post()
        self.assertFalse(bill.line_ids.filtered(lambda aml: aml.display_type == "cogs"))
        self._receive(order)
        self.assertEqual(self._balance(self.account_valuation), 1100.0, "recepția ia valoarea din factură")
        self.assertEqual(self._balance(self.account_src), 0.0)

    def test_partial_bills_correct_each_quantity(self):
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        self._bill(order, 110.0, qty=4.0).action_post()
        self.assertEqual(self._balance(self.account_valuation), 1040.0)
        self._bill(order, 120.0, qty=6.0).action_post()
        self.assertEqual(self._balance(self.account_valuation), 1160.0)
        self.assertEqual(self._balance(self.account_src), 0.0)

    def test_reset_to_draft_removes_correction(self):
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        bill = self._bill(order, 110.0)
        bill.action_post()
        self.assertTrue(bill.line_ids.filtered(lambda aml: aml.display_type == "cogs"))
        bill.button_draft()
        self.assertFalse(bill.line_ids.filtered(lambda aml: aml.display_type == "cogs"))

    def test_same_price_no_correction(self):
        order = self._purchase(10.0, 100.0)
        self._receive(order)
        bill = self._bill(order, 100.0)
        bill.action_post()
        self.assertFalse(bill.line_ids.filtered(lambda aml: aml.display_type == "cogs"))

    def _foreign_currency(self):
        company_currency = self.env.company.currency_id
        currency = (
            self.env.ref("base.USD") if company_currency != self.env.ref("base.USD") else self.env.ref("base.EUR")
        )
        currency.active = True
        today = fields.Date.today()
        for currency_rate_date, rate in ((today - timedelta(days=30), 2.0), (today + timedelta(days=5), 2.06)):
            self.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "name": currency_rate_date,
                    "rate": rate,
                    "company_id": self.env.company.id,
                }
            )
        return currency, today + timedelta(days=5)

    def test_exchange_rate_difference_does_not_change_stock(self):
        """Același preț în valută, curs −3% la factură: stocul rămâne la cursul
        recepției, diferența merge pe contul de câștig din diferențe de curs."""
        currency, invoice_date = self._foreign_currency()
        order = self._purchase(10.0, 100.0, currency=currency)
        self._receive(order)
        receipt_value = order.picking_ids.move_ids.value
        self.assertAlmostEqual(receipt_value, 500.0, places=2, msg="100 × 10 la cursul 2")
        bill = self._bill(order, 100.0, invoice_date=invoice_date)
        bill.action_post()
        self.assertAlmostEqual(self._balance(self.account_src), 0.0, places=2)
        self.assertAlmostEqual(self._balance(self.account_valuation), receipt_value, places=2)
        self.assertAlmostEqual(self.product.standard_price, receipt_value / 10.0, places=2)
        self.assertAlmostEqual(self._balance(self.account_fx_gain), -(500.0 - 1000.0 / 2.06), places=2)
        self.assertFalse(self._balance(self.account_fx_loss))

    def test_exchange_rate_and_price_difference(self):
        currency, invoice_date = self._foreign_currency()
        order = self._purchase(10.0, 100.0, currency=currency)
        self._receive(order)
        bill = self._bill(order, 110.0, invoice_date=invoice_date)
        bill.action_post()
        self.assertAlmostEqual(self._balance(self.account_src), 0.0, places=2)
        # stoc: 10 × 100 / 2 + diferența de preț (10 × 10 / 2)
        self.assertAlmostEqual(self._balance(self.account_valuation), 550.0, places=2)
        self.assertAlmostEqual(self._balance(self.account_fx_gain), -(550.0 - 1100.0 / 2.06), places=2)
