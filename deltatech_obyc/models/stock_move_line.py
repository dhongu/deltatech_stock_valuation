# © 2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import api, models

VALUATION_FIELDS = ["quantity", "location_id", "location_dest_id", "owner_id", "quant_id", "lot_id"]


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    # 20.0: adăugarea sau editarea liniilor unei mișcări validate reia valorizarea de la
    # data mișcării (`stock.move._set_value(recompute_date=...)`) și rescrie `value` pe
    # toate ieșirile ulterioare. Până în 19 se reevalua doar mișcarea editată: intrarea
    # din documentele ei, ieșirea proporțional cu corecția de cantitate. Notele OBYC sunt
    # postate din aceste valori, deci pentru produsele OBYC se păstrează comportamentul
    # din 19 (`obyc_defer_ml_valuation` face ca `stock.move._set_value` să le sară),
    # doar cu setarea companiei `valuation_keep_move_value` activă.

    @api.model_create_multi
    def create(self, vals_list):
        mls = super(StockMoveLine, self.with_context(obyc_defer_ml_valuation=True)).create(vals_list)
        mls = mls.with_env(self.env)
        mls._obyc_update_stock_move_value()
        return mls

    def write(self, vals):
        if not any(field in vals for field in VALUATION_FIELDS):
            return super().write(vals)
        old_qty_by_ml = {
            ml: ml.quantity
            for ml in self
            if ml.move_id and ml.move_id._obyc_keep_move_value() and (ml.move_id.is_in or ml.move_id.is_out)
        }
        res = super(StockMoveLine, self.with_context(obyc_defer_ml_valuation=True)).write(vals)
        if old_qty_by_ml:
            self.env["stock.move.line"].concat(*old_qty_by_ml)._obyc_update_stock_move_value(old_qty_by_ml)
        return res

    def _obyc_update_stock_move_value(self, old_qty_by_ml=None):
        """19.0 `stock.move.line._update_stock_move_value`, pentru mișcările OBYC."""
        old_qty_by_ml = old_qty_by_ml or {}
        moves_in = self.env["stock.move"]
        for move, mls in self.grouped("move_id").items():
            if not move or not move._obyc_keep_move_value() or not (move.is_in or move.is_out):
                continue
            if move.is_in:
                moves_in |= move
                continue
            delta = sum(ml.quantity - old_qty_by_ml.get(ml, 0) for ml in mls if not ml._should_exclude_for_valuation())
            if delta:
                move._obyc_correct_out_value(delta)
        if moves_in:
            moves_in._set_value()
