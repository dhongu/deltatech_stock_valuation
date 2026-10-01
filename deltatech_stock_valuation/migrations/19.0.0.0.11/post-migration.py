# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

# SV-006: rândurile create pentru altă companie decât cea curentă primeau moneda
# companiei curente. Sumele sunt în moneda companiei rândului, deci se corectează
# doar eticheta monetară.

from odoo.tools import SQL


def migrate(cr, version):
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
