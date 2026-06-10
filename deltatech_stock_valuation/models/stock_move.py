# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_price_unit(self):
        """Returnează prețul de descărcare din product.valuation pentru aria de evaluare
        corespunzătoare locației sursă. Dacă nu există evaluare, se folosește prețul standard."""
        self.ensure_one()

        use_valuation_area_price = self.product_id.categ_id.use_valuation_area_price
        if not use_valuation_area_price:
            return super()._get_price_unit()

        # Doar pentru ieșiri din stoc intern
        if self.location_id.usage != "internal":
            return super()._get_price_unit()

        valuation_area = self._get_valuation_area(raise_if_not_found=False)
        if not valuation_area:
            return super()._get_price_unit()

        _, _, _, account = self._get_accounting_data_for_valuation()

        if not account:
            return super()._get_price_unit()

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
        return super()._get_price_unit()
