# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_cogs_lines_vals(self):
        """Fără linii COGS pe factura de vânzare pentru produsele OBYC.

        La OBYC costul mărfii vândute se înregistrează la livrare, pe nota mișcării
        de stoc (cheia `stock_delivery`: Dr cheltuială / Cr stoc). Liniile COGS
        generate de core la postarea facturii (`_create_cogs_lines`) ar dubla costul;
        cu cheia `skip`, `_get_product_accounts` întoarce conturi goale pentru
        produsele OBYC și core-ul le sare. Produsele fără clasă de evaluare nu sunt
        afectate."""
        moves = self.with_context(transaction_key="skip")
        return super(AccountMove, moves)._get_cogs_lines_vals()
