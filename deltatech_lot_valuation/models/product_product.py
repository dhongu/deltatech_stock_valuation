# ©  2026 Deltatech
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_lot_stock_value(self, at_date=None):
        """Valoarea stocului produsului, adunată de pe loturi.

        Fără dată se adună valorile quanturilor din locațiile valorizate. Cu dată se folosește
        cantitatea fiecărui lot la acea dată înmulțită cu prețul curent al lotului: prețurile
        loturilor nu au istoric, deci raportul trebuie rulat după toate modificările de valoare
        (landed cost, facturi).
        """
        self.ensure_one()
        company = self.env.company
        if not at_date:
            quants = self.env["stock.quant"].search([("product_id", "=", self.id), ("company_id", "=", company.id)])
            return sum(quants.mapped("value"))
        at_date = fields.Datetime.to_datetime(at_date)
        lots = self.env["stock.lot"].search([("product_id", "=", self.id), ("company_id", "in", [company.id, False])])
        value = 0.0
        for lot in lots.with_context(to_date=at_date):
            qty = lot.product_qty
            if self.uom_id.is_zero(qty):
                continue
            if not lot._has_valuation_data():
                # lot fără preț propriu: nu are cum să fie valorizat pe lot, rămâne valoarea nucleului
                return self.with_context(to_date=at_date).total_value
            value += lot.inventory_value if self.tracking == "serial" else lot.unit_price * qty
        return value
