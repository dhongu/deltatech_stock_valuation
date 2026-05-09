# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    valuation_area_id = fields.Many2one(
        "valuation.area",
        string="Valuation Area",
        compute="_compute_valuation_area",
        store=True,
        readonly=False,
    )

    @api.constrains("product_id", "valuation_area_id", "account_id")
    def _check_valuation_area(self):
        """
        Check if valuation area is set on the account move line when required.
        """
        if not self.env.registry.ready:
            return

        for line in self:
            if not line.company_id.use_valuation_area:
                continue
            if line._is_valuation_area_required():
                raise UserError(
                    _(
                        "Valuation Area is required for stockable products. If the product is not stockable, you can leave it empty."
                    )
                )

    def _is_valuation_area_required(self):
        """
        Determine if valuation area is required for the current account move line.
        """
        self.ensure_one()
        if self.product_id and self.product_id.is_storable and not self.valuation_area_id:
            return True
        return False

    def _get_valuation_area(self, raise_if_not_found=True):
        """
        Get the appropriate valuation area for the current account move line.
        """
        self.ensure_one()
        if not self.company_id.use_valuation_area:
            return self.env["valuation.area"]
        valuation_area = self.valuation_area_id
        if not valuation_area:
            valuation_area = self.company_id.valuation_area_id

            stock_move = self.move_id.stock_move_id
            if "purchase_line_id" in self._fields:
                if self.purchase_line_id:
                    stock_move = next(iter(self.purchase_line_id.move_ids), None)
            if "sale_line_ids" in self._fields:
                if self.sale_line_ids:
                    stock_move = next(iter(self.sale_line_ids.mapped("move_ids")), None)
            if stock_move:
                valuation_area = stock_move._get_valuation_area(raise_if_not_found)
        if not valuation_area and raise_if_not_found:
            raise UserError(_("Valuation area is not defined"))

        return valuation_area

    @api.depends("product_id")
    def _compute_valuation_area(self):
        """
        Compute the valuation area for the account move lines.
        """
        if not self.env.registry.ready:
            return False
        for line in self:
            if line.product_id and line.company_id.use_valuation_area:
                valuation_area = line._get_valuation_area(raise_if_not_found=True)
            else:
                valuation_area = False
            line.valuation_area_id = valuation_area
