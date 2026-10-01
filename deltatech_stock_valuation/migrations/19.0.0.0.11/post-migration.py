# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

# SV-002 / SV-009: datele scrise de versiunea veche pe bazele cu mai multe companii
# (linii contabile și rânduri de evaluare pe aria altei companii) se repară.
# SV-006: rândurile create pentru altă companie decât cea curentă primeau moneda
# companiei curente. Sumele sunt în moneda companiei rândului, deci se corectează
# doar eticheta monetară.

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["product.valuation.history"]._cleanup_cross_company_rows()
    for table in ("product_valuation", "product_valuation_history"):
        cr.execute(
            SQL(
                """
                UPDATE %(table)s pv
                SET currency_id = c.currency_id
                FROM res_company c
                WHERE pv.company_id = c.id
                  AND pv.currency_id IS DISTINCT FROM c.currency_id
                """,
                table=SQL.identifier(table),
            )
        )
