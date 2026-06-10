# ©  2026 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com>
# See README.rst file on addons root folder for license details

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..models.product_valuation import (
    _PARAM_LAST_RUN,
    _PARAM_LAST_STEP,
    _PARAM_NOTIFY_UID,
    _PARAM_STEP,
    _PARAM_STEP5_LAST_PID,
)


@tagged("post_install", "-at_install", "deltatech_stock_valuation")
class TestConfigSettings(AccountTestInvoicingCommon):
    """
    Testări pentru acțiunile din configurări (res.config.settings): recalcularea
    pas cu pas, recalcularea evaluării curente, resetarea pasului și pornirea/oprirea
    refresh-ului automat, inclusiv restricțiile de securitate.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.valuation_area_level = "company"
        cls.env.company.use_valuation_area = True
        cls.env.company.set_stock_valuation_at_company_level()
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    def _new_settings(self, with_user=None):
        settings = self.env["res.config.settings"].create({"company_id": self.env.company.id})
        return settings if with_user is None else settings.with_user(with_user)

    def _normal_user(self):
        return self.env["res.users"].create(
            {
                "name": "Normal User",
                "login": "normal_user_cfg",
                "email": "normal_cfg@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_recompute_product_valuation_requires_system(self):
        """Recalcularea evaluării curente trebuie permisă doar administratorului de sistem."""
        with self.assertRaises(UserError):
            self._new_settings(with_user=self._normal_user()).recompute_product_valuation()

    def test_recompute_product_valuation_noop_when_not_company_level(self):
        """Recalcularea trebuie să se oprească fără efect dacă nivelul nu este 'company'."""
        self.env.company.valuation_area_level = "warehouse"
        # Nu trebuie să ridice eroare; pur și simplu se oprește.
        self.assertFalse(self._new_settings().recompute_product_valuation())

    def test_reset_refresh_step(self):
        """Resetarea pasului de refresh trebuie să readucă parametrii la valorile inițiale."""
        self.ICP.set_param(_PARAM_STEP, "4")
        self.ICP.set_param(_PARAM_STEP5_LAST_PID, "123")

        self._new_settings().reset_refresh_valuation_step()

        self.assertEqual(self.ICP.get_param(_PARAM_STEP), "1")
        self.assertEqual(self.ICP.get_param(_PARAM_STEP5_LAST_PID), "0")

    def test_reset_refresh_step_requires_system(self):
        """Resetarea pasului trebuie restricționată la administratorul de sistem."""
        with self.assertRaises(UserError):
            self._new_settings(with_user=self._normal_user()).reset_refresh_valuation_step()

    def test_start_stop_auto_refresh_toggles_cron(self):
        """Pornirea și oprirea refresh-ului automat trebuie să comute starea cron-ului."""
        cron = self.env.ref("deltatech_stock_valuation.ir_cron_auto_refresh_valuation")
        cron.sudo().active = False

        self._new_settings().start_auto_refresh()
        self.assertTrue(cron.active, "Auto refresh cron should be active after start")

        self._new_settings().stop_auto_refresh()
        self.assertFalse(cron.active, "Auto refresh cron should be inactive after stop")

    def test_refresh_full_cycle_resets_to_step_one(self):
        """
        Parcurgerea completă a celor 7 pași de refresh trebuie să readucă pasul la 1.
        """
        self.ICP.set_param(_PARAM_STEP, "1")
        self.ICP.set_param(_PARAM_STEP5_LAST_PID, "0")

        settings = self._new_settings()
        # Cel mult 12 apeluri pentru a acoperi eventualele iterații suplimentare la pasul 5.
        for _ in range(12):
            settings.refresh_stock_valuation()
            if self.ICP.get_param(_PARAM_STEP) == "1" and self.ICP.get_param(_PARAM_STEP5_LAST_PID) == "0":
                break

        self.assertEqual(self.ICP.get_param(_PARAM_STEP), "1", "Refresh cycle should reset to step 1")

    def test_action_recompute_in_background_requires_system(self):
        """Pornirea recalculării în background trebuie restricționată la administrator."""
        self.env.company.valuation_area_level = "company"
        with self.assertRaises(UserError):
            self._new_settings(with_user=self._normal_user()).action_recompute_in_background()

    def test_action_recompute_in_background_resets_and_starts_cron(self):
        """
        Acțiunea de background trebuie să repornească ciclul de la pasul 1, să rețină
        utilizatorul de notificat și să activeze cron-ul (declanșat imediat).
        """
        self.ICP.set_param(_PARAM_STEP, "4")
        self.ICP.set_param(_PARAM_STEP5_LAST_PID, "55")
        cron = self.env.ref("deltatech_stock_valuation.ir_cron_auto_refresh_valuation")
        cron.sudo().active = False

        self._new_settings().action_recompute_in_background()

        self.assertEqual(self.ICP.get_param(_PARAM_STEP), "1")
        self.assertEqual(self.ICP.get_param(_PARAM_STEP5_LAST_PID), "0")
        self.assertEqual(self.ICP.get_param(_PARAM_NOTIFY_UID), str(self.env.uid))
        self.assertTrue(cron.active, "Cron should be active after starting background recompute")

    def test_action_recompute_in_background_guards_double_start(self):
        """
        Dacă o recalculare rulează deja (cron activ), un nou click nu trebuie să
        repornească ciclul (nu resetează pasul), pentru a preveni dublul start.
        """
        cron = self.env.ref("deltatech_stock_valuation.ir_cron_auto_refresh_valuation")
        cron.sudo().active = True
        self.ICP.set_param(_PARAM_STEP, "3")

        result = self._new_settings().action_recompute_in_background()

        # Pasul nu trebuie resetat la 1 cât timp rulează.
        self.assertEqual(self.ICP.get_param(_PARAM_STEP), "3")
        self.assertEqual(result.get("tag"), "display_notification")

    def test_action_recompute_in_background_noop_when_not_company_level(self):
        """Acțiunea nu trebuie să facă nimic dacă nivelul nu este 'company'."""
        self.env.company.valuation_area_level = "warehouse"
        self.assertFalse(self._new_settings().action_recompute_in_background())

    def test_auto_refresh_step_records_progress(self):
        """
        Un pas de cron trebuie să avanseze pasul și să înregistreze progresul
        (ultimul pas executat și momentul rulării).
        """
        self.ICP.set_param(_PARAM_STEP, "1")
        self.env["product.valuation.history"]._auto_refresh_step()

        self.assertEqual(self.ICP.get_param(_PARAM_STEP), "2", "Step should advance after a cron run")
        self.assertEqual(self.ICP.get_param(_PARAM_LAST_STEP), "1", "Last executed step should be recorded")
        self.assertTrue(self.ICP.get_param(_PARAM_LAST_RUN), "Last run timestamp should be recorded")

    def test_refresh_step_info_label(self):
        """Câmpul informativ trebuie să reflecte pasul curent din parametri."""
        self.ICP.set_param(_PARAM_STEP, "2")
        settings = self._new_settings()
        settings._compute_refresh_valuation_step_info()
        self.assertIn("Step 2", settings.refresh_valuation_step_info)
