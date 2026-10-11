# ©  2008-2026 Deltatech
#              Dan Stoica <danila(@)terrabit(.)ro
# See README.rst file on addons root folder for license details

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockLot(models.Model):
    _inherit = "stock.lot"

    inventory_value = fields.Float("Inventory value")
    unit_price = fields.Float("Unit Price")
    input_price = fields.Float("Input Price")
    input_date = fields.Date(string="Input date")

    def _has_valuation_data(self):
        """Lotul are un preț propriu de la care se pot valoriza ieșirile și stocul."""
        self.ensure_one()
        return bool(self.unit_price or self.inventory_value)

    def _check_receipt_price_matches(self, unit_price, existing_qty):
        """Un lot care mai are stoc nu se poate recepționa la alt preț decât cel al ultimei recepții:
        prețul propriu al lotului nu poate reprezenta două costuri."""
        self.ensure_one()
        previous_price = self.input_price or self.unit_price
        digits = self.env["decimal.precision"].precision_get("Product Price")
        if float_compare(unit_price, previous_price, precision_digits=digits) != 0:
            raise UserError(
                self.env._(
                    "Lot %(lot)s of %(product)s still has %(qty)s in stock at %(old_price)s per unit, so it "
                    "cannot be received again at %(new_price)s. Use a different lot number for this "
                    "delivery or receive it at the same price.",
                    lot=self.name,
                    product=self.product_id.display_name,
                    qty=existing_qty,
                    old_price=previous_price,
                    new_price=unit_price,
                )
            )

