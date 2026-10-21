from odoo import models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        self._valuation_guard_check()
        return super()._action_done(cancel_backorder=cancel_backorder)

    def _valuation_guard_skip(self):
        """Extension point: moves validated outside the user's hands (e.g. a POS order) are not blocked."""
        self.ensure_one()
        return False

    def _valuation_guard_check(self):
        if self.env.context.get("skip_valuation_guard"):
            return
        errors = []
        for move in self:
            company = move.company_id
            if not company.valuation_guard_zero_cost or move.state in ("done", "cancel"):
                continue
            if not move.product_id.is_storable or move._valuation_guard_skip():
                continue
            product = move.product_id.with_company(company)
            rounding = company.currency_id.rounding
            if move._is_in():
                # the value the move will get at validation: bill, purchase order, return or cost
                value = move.with_company(company).sudo()._get_value()
                if float_compare(value, 0.0, precision_rounding=rounding) <= 0:
                    errors.append(
                        self.env._("%(product)s enters the stock with no value", product=product.display_name)
                    )
            elif move._is_out():
                if float_compare(product.standard_price, 0.0, precision_rounding=rounding) <= 0:
                    errors.append(self.env._("%(product)s has no cost", product=product.display_name))
        if errors:
            raise UserError(
                self.env._(
                    "These stock moves would carry no value:\n%(lines)s\n\n"
                    "Set the cost of the product, or the price on the purchase order, before validating.",
                    lines="\n".join(f"- {e}" for e in errors),
                )
            )
