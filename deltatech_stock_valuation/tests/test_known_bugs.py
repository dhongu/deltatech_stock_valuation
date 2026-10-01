# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..models.product_valuation import _PARAM_COMPANY, _PARAM_STEP, _PARAM_STEP5_LAST_PID


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestKnownBugs(AccountTestInvoicingCommon):
    """
    Teste de regresie pentru constatările din readme/bugs.md (SV-001..SV-007).
    Două companii (A = compania testului, B = compania a doua, în EUR) folosesc
    același cont de stoc, ca pe bazele multi-company reale.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_data_b = cls.setup_other_company(name="Company B SV", currency_id=cls.env.ref("base.EUR").id)
        cls.company_b = cls.company_data_b["company"]
        cls.env.ref("base.EUR").active = True
        cls.env.user.company_ids |= cls.company_b

        cls.account_stock_val = cls.env["account.account"].create(
            {
                "name": "Stock Valuation KB",
                "code": "SVKB1",
                "account_type": "asset_current",
                "is_for_stock_valuation": True,
            }
        )
        # contul e partajat de ambele companii, cu același cod
        cls.account_stock_val.sudo().with_company(cls.company_b).code = "SVKB1"
        cls.account_stock_val.company_ids = [(4, cls.company_b.id)]
        for company in cls.company_a | cls.company_b:
            company.valuation_area_level = "company"
            company.use_valuation_area = True
            company.with_company(company).set_stock_valuation_at_company_level()
        cls.area_a = cls.company_a.valuation_area_id
        cls.area_b = cls.company_b.valuation_area_id

        cls.product = cls.product_a
        cls.product.is_storable = True
        cls.product_b_only = cls.product_b
        cls.product_b_only.is_storable = True

    def _create_entry(self, company, product, debit, quantity, area=None):
        """Notă de intrare în stoc (cantitate semnată pozitivă pe debit) în compania dată."""
        data = self.company_data if company == self.company_a else self.company_data_b
        line = {
            "name": "Stock line",
            "account_id": self.account_stock_val.id,
            "debit": debit,
            "credit": 0.0,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": quantity,
        }
        if area:
            line["valuation_area_id"] = area.id
        return (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "journal_id": data["default_journal_misc"].id,
                    "date": fields.Date.today(),
                    "line_ids": [
                        (0, 0, line),
                        (
                            0,
                            0,
                            {
                                "name": "Counterpart",
                                "account_id": data["default_account_expense"].id,
                                "debit": 0.0,
                                "credit": debit,
                            },
                        ),
                    ],
                }
            )
        )

    def _history(self, company, product, area):
        return self.env["product.valuation.history"].search(
            [
                ("product_id", "=", product.id),
                ("valuation_area_id", "=", area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", company.id),
                ("month", "=", fields.Date.today().strftime("%Y%m")),
            ]
        )

    def _valuation(self, company, product, area):
        return self.env["product.valuation"].search(
            [
                ("product_id", "=", product.id),
                ("valuation_area_id", "=", area.id),
                ("account_id", "=", self.account_stock_val.id),
                ("company_id", "=", company.id),
            ]
        )

    def _stock_line(self, move):
        return move.line_ids.filtered(lambda line: line.account_id == self.account_stock_val)

    # SV-001 ------------------------------------------------------------------

    def test_sv001_posting_counts_line_without_uom(self):
        """O linie de stoc fără unitate de măsură e numărată la postare la fel ca la
        recalculul complet (cu unitatea produsului)."""
        move = self._create_entry(self.company_a, self.product, 1000.0, 10.0)
        line = self._stock_line(move)
        # NULL apare la import / SQL / migrare: nucleul completează UoM-ul pe draft
        self.env.cr.execute("UPDATE account_move_line SET product_uom_id = NULL WHERE id = %s", [line.id])
        line.invalidate_recordset(["product_uom_id"])
        move.action_post()

        history = self._history(self.company_a, self.product, self.area_a)
        self.assertEqual(history.quantity, 10.0)
        self.assertEqual(history.amount, 1000.0)
        valuation = self._valuation(self.company_a, self.product, self.area_a)
        self.assertEqual(valuation.quantity, 10.0)
        self.assertEqual(valuation.amount, 1000.0)

        self.env["product.valuation.history"]._recompute_all_amount()
        self.env["product.valuation"]._recompute_all_amount()
        valuation = self._valuation(self.company_a, self.product, self.area_a)
        self.assertEqual(valuation.quantity, 10.0)
        self.assertEqual(valuation.amount, 1000.0)

    # SV-002 ------------------------------------------------------------------

    def test_sv002_company_level_update_is_scoped_to_company(self):
        """Setarea ariei la nivel de companie mută doar liniile companiei curente,
        inclusiv pe cele fără arie, și nu atinge liniile altei companii."""
        move_b = self._create_entry(self.company_b, self.product, 500.0, 5.0, area=self.area_b)
        move_b.with_company(self.company_b).action_post()
        move_a = self._create_entry(self.company_a, self.product, 1000.0, 10.0)
        move_a.action_post()
        line_a = self._stock_line(move_a)
        self.env.cr.execute("UPDATE account_move_line SET valuation_area_id = NULL WHERE id = %s", [line_a.id])

        self.company_a.set_stock_valuation_at_company_level()
        self.env.invalidate_all()

        self.assertEqual(self._stock_line(move_b).valuation_area_id, self.area_b)
        self.assertEqual(line_a.valuation_area_id, self.area_a)

    # SV-003 ------------------------------------------------------------------

    def test_sv003_background_refresh_runs_on_start_company(self):
        """Recalculul în fundal pornit din compania B reface B, chiar dacă cronul
        rulează cu compania implicită A, și nu atinge istoricul lui A."""
        self._create_entry(self.company_a, self.product, 1000.0, 10.0).action_post()
        move_b = self._create_entry(self.company_b, self.product, 500.0, 5.0, area=self.area_b)
        move_b.with_company(self.company_b).action_post()
        history_a = self._history(self.company_a, self.product, self.area_a)
        self.assertTrue(history_a)
        # evaluarea lui B e veche/inexistentă: trebuie refăcută de recalcul
        self.env.cr.execute("DELETE FROM product_valuation WHERE company_id = %s", [self.company_b.id])

        settings_b = self.env["res.config.settings"].with_company(self.company_b).create({})
        self.assertEqual(settings_b.company_id, self.company_b)
        settings_b.action_recompute_in_background()
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_int(_PARAM_COMPANY), self.company_b.id)

        # cronul rulează în mediul utilizatorului lui, cu compania A
        cron_model = self.env["product.valuation.history"].with_company(self.company_a)
        for _i in range(7):
            cron_model._auto_refresh_step()
        self.env.invalidate_all()

        valuation_b = self._valuation(self.company_b, self.product, self.area_b)
        self.assertEqual(valuation_b.quantity, 5.0)
        self.assertEqual(valuation_b.amount, 500.0)
        self.assertTrue(history_a.exists(), "istoricul lui A nu trebuie șters de recalculul lui B")
        self.assertEqual(history_a.quantity_final, 10.0)
        self.assertFalse(self.env["ir.config_parameter"].sudo().get_int(_PARAM_COMPANY))

    def test_sv003_manual_step_refuses_other_company(self):
        """Un recalcul pas cu pas început în A nu poate fi continuat din B."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_int(_PARAM_STEP, 1)
        ICP.set_int(_PARAM_STEP5_LAST_PID, 0)
        self.env["res.config.settings"].create({}).refresh_stock_valuation()
        self.assertEqual(ICP.get_int(_PARAM_STEP), 2)
        self.assertEqual(ICP.get_int(_PARAM_COMPANY), self.company_a.id)

        settings_b = self.env["res.config.settings"].with_company(self.company_b).create({})
        with self.assertRaises(UserError):
            settings_b.refresh_stock_valuation()
        self.assertEqual(ICP.get_int(_PARAM_STEP), 2)

        settings_b.reset_refresh_valuation_step()
        self.assertFalse(ICP.get_int(_PARAM_COMPANY))

    def test_sv003_full_recompute_steps_are_scoped_to_company(self):
        """Pașii 2, 3, 4 și 6 ai recalculului complet nu citesc și nu modifică
        istoricul altei companii (pasul 2 dădea și unique violation)."""
        self._create_entry(self.company_a, self.product, 1000.0, 10.0).action_post()
        move_b = self._create_entry(self.company_b, self.product_b_only, 500.0, 5.0, area=self.area_b)
        move_b.with_company(self.company_b).action_post()
        history_b = self._history(self.company_b, self.product_b_only, self.area_b)
        self.assertEqual(history_b.quantity_final, 5.0)

        History = self.env["product.valuation.history"]
        History._recompute_all_amount(execute_step=[1, 2, 3])
        self.env.invalidate_all()
        rows_a = History.search([("company_id", "=", self.company_a.id)])
        self.assertNotIn(self.product_b_only, rows_a.product_id, "pasul 3 nu trebuie să copieze produsele lui B în A")
        self.assertTrue(history_b.exists())

        History._recompute_all_amount(execute_step=[4, 5, 6])
        self.env.invalidate_all()
        self.assertEqual(self._history(self.company_a, self.product, self.area_a).quantity_final, 10.0)
        self.assertEqual(history_b.quantity_final, 5.0)
        self.assertEqual(History.search_count([("company_id", "=", self.company_b.id)]), 1)

    # SV-004 ------------------------------------------------------------------

    def test_sv004_product_valuation_table_is_read_only(self):
        """Tabelul de evaluare de pe produs nu permite adăugarea de rânduri, iar
        utilizatorul intern nu poate crea evaluări; postarea le actualizează în continuare."""
        arch = self.env.ref("deltatech_stock_valuation.product_template_form_view").arch
        node = etree.fromstring(arch).xpath("//field[@name='product_valuation_ids']/list")[0]
        self.assertEqual(node.get("create"), "0")

        user = self.env["res.users"].create(
            {
                "name": "Billing User SV",
                "login": "billing_user_sv",
                "group_ids": [(6, 0, [self.env.ref("account.group_account_invoice").id])],
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, self.company_a.ids)],
            }
        )
        with self.assertRaises(AccessError):
            self.env["product.valuation"].with_user(user).create(
                {
                    "product_id": self.product.id,
                    "valuation_area_id": self.area_a.id,
                    "account_id": self.account_stock_val.id,
                    "company_id": self.company_a.id,
                }
            )
        move = self._create_entry(self.company_a, self.product, 1000.0, 10.0)
        move.action_post()
        keys = move._get_valuation_keys()
        self.env.cr.execute("DELETE FROM product_valuation WHERE company_id = %s", [self.company_a.id])
        self.env["account.move"].with_user(user)._recompute_valuation_keys(keys)
        self.assertEqual(self._valuation(self.company_a, self.product, self.area_a).quantity, 10.0)

    # SV-006 ------------------------------------------------------------------

    def test_sv006_new_rows_use_currency_of_their_company(self):
        """Rândurile noi create pentru o companie explicită primesc moneda ei,
        nu moneda companiei curente din mediu."""
        self.assertNotEqual(self.company_a.currency_id, self.company_b.currency_id)
        env_a = self.env["product.valuation"].with_company(self.company_a)
        valuation = env_a.get_valuation(self.product.id, self.area_b.id, self.account_stock_val.id, self.company_b.id)
        self.assertEqual(valuation.currency_id, self.company_b.currency_id)
        history = (
            self.env["product.valuation.history"]
            .with_company(self.company_a)
            .get_valuation(
                self.product.id, self.area_b.id, self.account_stock_val.id, fields.Date.today(), self.company_b.id
            )
        )
        self.assertEqual(history.currency_id, self.company_b.currency_id)

    # SV-007 ------------------------------------------------------------------

    def test_sv007_recompute_all_server_action(self):
        """Acțiunea server „Recompute All Stock Valuation” rulează pentru administrator
        și e refuzată pentru un utilizator obișnuit."""
        self._create_entry(self.company_a, self.product, 1000.0, 10.0).action_post()
        self.env.cr.execute("DELETE FROM product_valuation WHERE company_id = %s", [self.company_a.id])
        action = self.env.ref("deltatech_stock_valuation.action_product_valuation_history_recompute")
        action.run()
        self.assertEqual(self._valuation(self.company_a, self.product, self.area_a).quantity, 10.0)

        user = self.env["res.users"].create(
            {
                "name": "Normal User SV",
                "login": "normal_user_sv",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            action.with_user(user).run()

    # curățarea datelor vechi (M1 din verificarea Pacioli) și invariantul de sold ----------

    def test_cleanup_cross_company_rows_from_old_version(self):
        """Actualizarea readuce pe aria companiei liniile mutate de versiunea veche și
        șterge evaluările / istoricul rămase pe aria altei companii."""
        move_b = self._create_entry(self.company_b, self.product_b_only, 500.0, 5.0, area=self.area_b)
        move_b.with_company(self.company_b).action_post()
        line_b = self._stock_line(move_b)
        History = self.env["product.valuation.history"]
        # starea lăsată de versiunea veche: linia lui B pe aria lui A, istoric (B, arie A)
        self.env.cr.execute(
            "UPDATE account_move_line SET valuation_area_id = %s WHERE id = %s", [self.area_a.id, line_b.id]
        )
        self.env.cr.execute(
            "UPDATE product_valuation_history SET valuation_area_id = %s WHERE company_id = %s",
            [self.area_a.id, self.company_b.id],
        )
        History.invalidate_model()

        History._cleanup_cross_company_rows()

        self.assertEqual(line_b.valuation_area_id, self.area_b)
        self.assertFalse(
            History.search([("company_id", "=", self.company_b.id), ("valuation_area_id", "=", self.area_a.id)])
        )

        History.with_company(self.company_b)._recompute_all_amount()
        self.env["product.valuation"].with_company(self.company_b)._recompute_all_amount()
        self.assertEqual(self._valuation(self.company_b, self.product_b_only, self.area_b).amount, 500.0)

    def test_full_recompute_matches_account_balance_per_company(self):
        """După recalculul complet al ambelor companii, valoarea evaluată pe cont și companie
        este egală cu soldul contului de stoc al companiei."""
        self._create_entry(self.company_a, self.product, 1000.0, 10.0).action_post()
        self._create_entry(self.company_a, self.product_b_only, 300.0, 3.0).action_post()
        move_b = self._create_entry(self.company_b, self.product, 500.0, 5.0, area=self.area_b)
        move_b.with_company(self.company_b).action_post()

        for company in self.company_a | self.company_b:
            self.env["product.valuation.history"].with_company(company)._recompute_all_amount()
            self.env["product.valuation"].with_company(company)._recompute_all_amount()

        for company in self.company_a | self.company_b:
            balance = sum(
                self.env["account.move.line"]
                .search(
                    [
                        ("account_id", "=", self.account_stock_val.id),
                        ("company_id", "=", company.id),
                        ("parent_state", "=", "posted"),
                    ]
                )
                .mapped("balance")
            )
            valued = sum(
                self.env["product.valuation"]
                .search([("account_id", "=", self.account_stock_val.id), ("company_id", "=", company.id)])
                .mapped("amount")
            )
            self.assertAlmostEqual(valued, balance, places=2, msg=company.name)
