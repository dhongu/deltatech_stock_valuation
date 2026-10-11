# © 2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import models


class StockValuationAdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    def _create_accounting_entries(self, remaining_qty):
        """Pentru produsele cu loturi, partea de landed cost capitalizată în stoc se calculează pe
        cantitatea rămasă din recepție pe loturi (cea pe care o folosește și prețul lotului), nu pe
        restul FIFO pe produs calculat de nucleu."""
        move = self.move_id
        if move.move_line_ids and move.product_id.tracking != "none" and all(ml.lot_id for ml in move.move_line_ids):
            remaining_qty = move._get_lot_remaining_qty()
        return super()._create_accounting_entries(remaining_qty)
