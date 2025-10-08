
from odoo import models

class StockValuationAdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'


    def _create_accounting_entries(self, remaining_qty):
        transaction_key = 'landed_cost'
        valuation_area = self.move_id._get_valuation_area()
        account_modifier = self.cost_id.account_journal_id.account_modifier_id
        self = self.with_context(transaction_key=transaction_key, valuation_area=valuation_area, account_modifier=account_modifier)
        return super()._create_accounting_entries(remaining_qty)


