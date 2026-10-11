# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def stock_value(self, accounts_by_product=None, at_date=None):
        """Valoarea stocului pe conturi (raportul „Stock Valuation” și închiderea evaluării).

        Pentru produsele cu urmărire valoarea se ia de pe loturi, nu de pe totalul calculat de nucleu
        pe produs: nucleul consideră consumate cele mai vechi unități (FIFO sau medie), pe când
        ieșirile se valorizează pe lotul livrat.
        """
        self.ensure_one()
        if not accounts_by_product:
            accounts_by_product = self.with_context(prefetch_fields=False)._get_accounts_by_product()
        value_by_account = super().stock_value(accounts_by_product, at_date=at_date)
        for product, accounts in accounts_by_product.items():
            if product.tracking == "none":
                continue
            product = product.with_company(self)
            core_value = product.with_context(to_date=at_date).total_value
            value_by_account[accounts["valuation"]] += product._get_lot_stock_value(at_date) - core_value
        return value_by_account
