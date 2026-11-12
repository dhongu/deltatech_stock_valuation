# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import models

SKIP_ENTRY_CONTEXT_KEY = "skip_stock_valuation_entry"


class StockMove(models.Model):
    _inherit = "stock.move"

    def _should_create_account_move(self):
        """The reclassification document posts its own journal entry: the moves of its transfers
        must not generate the automatic valuation entry as well."""
        if self.env.context.get(SKIP_ENTRY_CONTEXT_KEY):
            return False
        return super()._should_create_account_move()
