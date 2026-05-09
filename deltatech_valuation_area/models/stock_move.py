import logging

from odoo import _, models
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
                    _("Source and destination locations must have the same valuation area for internal moves.")
                )
        if not valuation_area and raise_if_not_found:
            raise UserError(_("Valuation area is not defined"))
        return valuation_area

    def _prepare_account_move_line(self, qty, cost, credit_account_id, debit_account_id, svl_id, description):
        """
        Inject the valuation area into the account move line values.
        """
        res = super()._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, svl_id, description)
        if not self.company_id.use_valuation_area:
            return res
        valuation_area = self._get_valuation_area()
        for line in res:
            product_id = line[2].get("product_id")
            if product_id:
                line[2].update({"valuation_area_id": valuation_area.id})
        return res
