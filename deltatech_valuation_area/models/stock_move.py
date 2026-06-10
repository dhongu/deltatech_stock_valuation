import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_valuation_area(self, raise_if_not_found=True):
        """
        Get the valuation area for the stock move based on locations and warehouse.
        """
        self.ensure_one()
        if not self.company_id.use_valuation_area:
            return self.env["valuation.area"]
        valuation_area = self.company_id.valuation_area_id
        if self.warehouse_id.valuation_area_id:
            valuation_area = self.warehouse_id.valuation_area_id
        if self.location_id.valuation_area_id and self.location_id.usage == "internal":
            valuation_area = self.location_id.valuation_area_id
        if self.location_dest_id.valuation_area_id and self.location_dest_id.usage == "internal":
            valuation_area = self.location_dest_id.valuation_area_id
        if self.location_id.usage == "internal" and self.location_dest_id.usage == "internal":
            if self.location_id.valuation_area_id != self.location_dest_id.valuation_area_id:
                raise UserError(
                    self.env._("Source and destination locations must have the same valuation area for internal moves.")
                )
        if not valuation_area and raise_if_not_found:
            raise UserError(self.env._("Valuation area is not defined"))
        return valuation_area

    def _get_account_move_line_vals(self):
        """
        Inject the valuation area, quantity and UoM into the account move line values.

        Nota: în Odoo 19 hook-ul core este `_get_account_move_line_vals` (vechiul
        `_prepare_account_move_line` nu mai există), iar liniile generate de core nu
        poartă cantitate/UoM — fără ele evaluarea ar pierde cantitățile pe notele
        de stoc.
        """
        vals_list = super()._get_account_move_line_vals()
        quantity = self._get_valued_qty()
        valuation_area = (
            self._get_valuation_area(raise_if_not_found=False) if self.company_id.use_valuation_area else False
        )
        for vals in vals_list:
            if not vals.get("product_id"):
                continue
            # convenție: cantitate SEMNATĂ — pozitivă pe linia de debit (intrare),
            # negativă pe linia de credit (ieșire); agregările din evaluare se bazează pe ea
            signed_quantity = -quantity if vals.get("credit") else quantity
            vals.setdefault("quantity", signed_quantity)
            vals.setdefault("product_uom_id", self.product_id.uom_id.id)
            if valuation_area:
                vals["valuation_area_id"] = valuation_area.id
        return vals_list
