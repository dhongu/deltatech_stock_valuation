# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # def _is_valuation_area_required(self):
    #     """
    #     Extend requirement check to only include accounts marked for stock valuation.
    #     """
    #     res = super()._is_valuation_area_required()
    #     if res:
    #         return self.account_id.is_for_stock_valuation
    #     return res
