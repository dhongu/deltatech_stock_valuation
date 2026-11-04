# ©  2026 Terrabit
# See README.rst file on addons root folder for license details
#
# Capturi de ecran pentru fișa consultant (RO) și pentru readme/USAGE.md (EN) ale modulului
# `deltatech_stock_valuation_guard_pos`, generate în timpul testelor, pe planul de conturi RO.
#
# Seed determinist: compania „RO Company" cu Block Unvalued Moves pornit, casa de marcat
# „Magazin" (plată numerar) cu sesiunea deschisă și două produse stocabile vândute în POS:
# „Marfă fără cost" (cost 0) și „Marfă cu cost" (cost 25). Captura arată mesajul primit de
# casier când adaugă în coș produsul fără cost.
#
# Rulare:
#   ./odoo/odoo-bin -c odoo.conf -d test19 -i l10n_ro,deltatech_stock_valuation_guard_pos,deltatech_doc_screenshots \
#       --test-tags=fise_screenshots --stop-after-init --http-port=8170
import unittest

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

try:
    from odoo.addons.deltatech_doc_screenshots.tests.screenshot_case import ScreenshotCase
except ImportError:
    ScreenshotCase = None


@tagged("-at_install", "post_install", "fise_screenshots")
class TestValuationGuardPosScreenshots(AccountTestInvoicingCommon, ScreenshotCase or object):
    screenshots_module = "deltatech_stock_valuation_guard_pos"

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ro")
    def setUpClass(cls):
        if ScreenshotCase is None:
            raise unittest.SkipTest("deltatech_doc_screenshots indisponibil")
        super().setUpClass()
        cls.prepare_ro_company(name="RO Company")
        env = cls.env
        company = env.company
        env.ref("base.user_admin").write(
            {
                "company_ids": [(4, company.id)],
                "company_id": company.id,
                "group_ids": [(4, env.ref("point_of_sale.group_pos_manager").id)],
            }
        )
        company.write({"cost_method": "average", "inventory_valuation": "real_time", "valuation_guard_zero_cost": True})

        product_vals = {"is_storable": True, "available_in_pos": True, "list_price": 50.0}
        cls.product_no_cost = env["product.product"].create(dict(product_vals, name="Marfă fără cost"))
        env["product.product"].create(dict(product_vals, name="Marfă cu cost", standard_price=25.0))

        cash_journal = env["account.journal"].search(
            [("type", "=", "cash"), ("company_id", "=", company.id)], limit=1
        ) or env["account.journal"].create({"name": "Casa", "type": "cash", "code": "CSH", "company_id": company.id})
        payment_method = env["pos.payment.method"].create(
            {"name": "Numerar", "journal_id": cash_journal.id, "company_id": company.id}
        )
        cls.config = env["pos.config"].create(
            {"name": "Magazin", "company_id": company.id, "payment_method_ids": [(6, 0, payment_method.ids)]}
        )
        cls.config.open_ui()
        cls.config.current_session_id.set_opening_control(0, "")

    def _shots(self):
        return [
            {
                "path": f"/pos/ui?config_id={self.config.id}",
                "name": "01_pos_produs_fara_cost.png",
                "wait": ".product-list",
                "timeout": 60000,
                "click_btn": ".product-list article:has-text('Marfă fără cost')",
                "wait_after": ".modal-dialog",
                "hide_chatter": False,
                "settle": 1500,
            },
        ]

    def test_capture_fise(self):
        self.capture_screenshots(self._shots())

    def test_capture_usage(self):
        self.capture_screenshots(self._shots(), lang="en_US")
