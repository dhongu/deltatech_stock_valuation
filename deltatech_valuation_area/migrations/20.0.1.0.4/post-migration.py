# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Load the corrected Romanian translations over the old ones.

    An upgrade loads the .po files without overwriting: the texts unified in ro.po
    ("Zonă de evaluare" → "Arie de evaluare") would keep their old wording on an
    existing database.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.module.module"].search([("name", "=", "deltatech_valuation_area")])._update_translations(overwrite=True)
