# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    # Valorizarea ieșirilor trece prin _set_value (din Odoo 19); prețul pe aria de
    # evaluare se aplică ca post-procesare peste _set_value.
    #
    # Odoo 20:
    # - `stock.move.value` e NEGATIV pe ieșiri (în 19 era pozitiv);
    # - `_set_value(correction_quantity=...)` a dispărut: corecțiile (dată schimbată,
    #   cantitate editată pe o mișcare efectuată, intrare revalorizată după ce stocul a
    #   fost deja descărcat) trec prin `_set_value(recompute_date=...)`, care reia
    #   valorizarea tuturor mișcărilor ulterioare ale produsului
    #   (`product.product._correct_inventory_valuation`) și RESCRIE valoarea ieșirilor la
    #   costul mediu/standard global. Pentru ieșirile valorizate la prețul ariei se
    #   păstrează, ca în 19, prețul unitar cu care au fost descărcate.

    def _dsv_uses_valuation_area_price(self):
        """Ieșirea din stoc intern a unui produs cu `use_valuation_area_price`
        (nu FIFO, nu valorizat pe lot) se valorizează la prețul ariei."""
        self.ensure_one()
        product = self.product_id.with_company(self.company_id)
        if not product.categ_id.use_valuation_area_price:
            return False
        if product.lot_valuated or product.cost_method == "fifo":
            # lot_valuated: core valorizează per lot; fifo: stiva FIFO din core
            return False
        if self.location_id.usage != "internal":
            return False
        return bool(self.is_out or self._is_out())

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

    def _dsv_apply_valuation_area_price(self):
        """Valorizează ieșirile la prețul din product.valuation (valoare negativă în 20)."""
        for move in self:
            if not move._dsv_uses_valuation_area_price():
                continue
            price = move._get_valuation_area_price()
            if price is not None:
                move.value = -price * move._get_valued_qty()

    def _dsv_area_priced_out_moves(self, recompute_date):
        """Ieșirile efectuate, valorizate la prețul ariei, pe care reluarea din core
        (`_correct_inventory_valuation`) le poate rescrie: aceleași produse, de la
        `recompute_date` încolo, plus mișcările din recordset."""
        domain = [
            ("product_id", "in", self.product_id.ids),
            ("date", ">=", recompute_date),
            ("is_out", "=", True),
            ("state", "=", "done"),
        ]
        moves = self.env["stock.move"].search(domain) | self.filtered("is_out")
        return moves.filtered(lambda m: m._dsv_uses_valuation_area_price())

    def _set_value(self, recompute_date=None, skip_check=False):
        """Post-procesare: ieșirile din stoc intern ale produselor cu
        `use_valuation_area_price` se valorizează la prețul din product.valuation
        pentru aria locației sursă (în loc de prețul standard/CMP global)."""
        if not recompute_date:
            res = super()._set_value(recompute_date=recompute_date, skip_check=skip_check)
            self._dsv_apply_valuation_area_price()
            return res

        # Corecție/reluare: se reține prețul unitar cu care a fost descărcată fiecare
        # ieșire la prețul ariei și se reaplică după reluarea din core.
        # `dsv_previous_valued_qty` (pus de stock.move.line la editarea cantității)
        # dă cantitatea dinainte de corecție, ca prețul unitar să rămână cel inițial
        # (echivalentul corecției proporționale `correction_quantity` din 19).
        previous_qty = self.env.context.get("dsv_previous_valued_qty") or {}
        unit_prices = {}
        for move in self._dsv_area_priced_out_moves(recompute_date):
            if not move.value:
                continue
            qty = previous_qty.get(move.id) or move._get_valued_qty()
            if qty:
                unit_prices[move] = -move.value / qty

        res = super()._set_value(recompute_date=recompute_date, skip_check=skip_check)

        for move, unit_price in unit_prices.items():
            value = -unit_price * move._get_valued_qty()
            if move.value != value:
                move.value = value
        # ieșirile fără valoare încă (ex. linie adăugată pe o mișcare nevalorizată)
        self.filtered(lambda m: m not in unit_prices)._dsv_apply_valuation_area_price()
        return res
