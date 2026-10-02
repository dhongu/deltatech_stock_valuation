# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    valuation_area_id = fields.Many2one("valuation.area", string="Valuation Area")

    def _get_valuation_area(self):
        """Aria locației: cea proprie, altfel aria depozitului căruia îi aparține locația."""
        self.ensure_one()
        return self.valuation_area_id or self.warehouse_id.valuation_area_id
