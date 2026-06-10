# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    # În Odoo 19 valorizarea ieșirilor nu mai trece prin _get_price_unit (care acum
    # derivă prețul unitar al unei mișcări existente), ci prin _set_value. Prețul pe
    # aria de evaluare se aplică deci ca post-procesare peste _set_value.

    def _get_valuation_area_price(self):
        """Returnează prețul de descărcare din product.valuation pentru aria de evaluare
        corespunzătoare locației sursă, sau None dacă nu există evaluare utilizabilă."""
        self.ensure_one()

        valuation_area = self._get_valuation_area(raise_if_not_found=False)
        if not valuation_area:
            return None

        accounts = self.product_id.product_tmpl_id.get_product_accounts()
        account = accounts.get("stock_valuation")
        if not account:
            return None

        valuation = self.env["product.valuation"].search(
            [
                ("product_id", "=", self.product_id.id),
                ("valuation_area_id", "=", valuation_area.id),
                ("account_id", "=", account.id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if valuation and valuation.price:
            return valuation.price

        _logger.warning(
            "deltatech_stock_valuation: nu există evaluare pentru produsul %s "
            "în aria %s — se folosește prețul standard",
            self.product_id.display_name,
            valuation_area.display_name,
        )
        return None

    def _set_value(self, correction_quantity=None):
        """Post-procesare: ieșirile din stoc intern ale produselor cu
        `use_valuation_area_price` se valorizează la prețul din product.valuation
        pentru aria locației sursă (în loc de prețul standard/CMP global)."""
        res = super()._set_value(correction_quantity=correction_quantity)
        if correction_quantity:
            # corecțiile de cantitate sunt ajustate proporțional de super(),
            # pornind de la o valoare care era deja la prețul ariei
            return res
        for move in self:
            if not (move.is_out or move._is_out()):
                continue
            if not move.product_id.categ_id.use_valuation_area_price:
                continue
            if move.product_id.lot_valuated or move.product_id.cost_method == "fifo":
                # lot_valuated: core valorizează per lot; fifo: straturi core
                continue
            if move.location_id.usage != "internal":
                continue
            price = move._get_valuation_area_price()
            if price is not None:
                move.value = price * move._get_valued_qty()
        return res
