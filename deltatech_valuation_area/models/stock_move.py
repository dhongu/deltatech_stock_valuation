import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_valuation_area(self, raise_if_not_found=True):
        """
        Get the valuation area for the stock move based on locations and warehouse.

        Aria se ia din locația internă (cea proprie sau a depozitului locației, destinația
        având prioritate), apoi din depozitul de aprovizionare al mișcării și, la final, din
        companie. `stock.move.warehouse_id` e câmpul de procurement, gol pe ajustările de
        inventar și pe transferurile manuale, de aceea depozitul se deduce din locație.
        """
        self.ensure_one()
        if not self.company_id.use_valuation_area:
            return self.env["valuation.area"]
        valuation_area = self.company_id.valuation_area_id
        if self.warehouse_id.valuation_area_id:
            valuation_area = self.warehouse_id.valuation_area_id
        for location in (self.location_id, self.location_dest_id):
            if location.usage == "internal" and location._get_valuation_area():
                valuation_area = location._get_valuation_area()
        if not valuation_area and raise_if_not_found:
            raise UserError(self.env._("Valuation area is not defined"))
        return valuation_area

    def _check_internal_move_valuation_area(self):
        """Mișcările între două locații interne trebuie să rămână în aceeași arie.

        Verificarea rulează la validarea mișcării: în Odoo 19 o mișcare intern→intern nu
        generează notă contabilă, deci nu se poate baza pe generarea liniilor contabile.
        Trecerea între arii se face printr-o locație de tranzit.
        """
        for move in self:
            if not move.company_id.use_valuation_area:
                continue
            default_area = move.company_id.valuation_area_id
            # liniile pot avea alte locații decât mișcarea (putaway pe o sublocație)
            location_pairs = {(move.location_id, move.location_dest_id)}
            location_pairs |= {(line.location_id, line.location_dest_id) for line in move.move_line_ids}
            for location, location_dest in location_pairs:
                if location.usage != "internal" or location_dest.usage != "internal":
                    continue
                source_area = location._get_valuation_area() or default_area
                dest_area = location_dest._get_valuation_area() or default_area
                if source_area != dest_area:
                    raise UserError(
                        self.env._(
                            "Source and destination locations must have the same valuation area for internal moves."
                        )
                    )

    def _action_done(self, cancel_backorder=False):
        self._check_internal_move_valuation_area()
        return super()._action_done(cancel_backorder=cancel_backorder)

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
