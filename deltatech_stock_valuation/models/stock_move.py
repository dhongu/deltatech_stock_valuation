# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details


from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"



    # pretul de iesire din stoc se va calula in functie de aria de evaluare
    def _get_price_unit(self):
        return super()._get_price_unit()
