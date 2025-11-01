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

    # _sql_constraints = [
    #     ('valuation_area_id_required',
    #      'CHECK(valuation_area_id IS NOT NULL OR product_id IS NULL)',
    #      _('Valuation Area is required for stockable products. If the product is not stockable, you can leave it empty.'))
    # ]
    @api.constrains("product_id")
    def _check_valuation_area(self):
        for line in self:
            if line.product_id and line.product_id.is_storable and not line.valuation_area_id:
                raise UserError(
                    _(
                        "Valuation Area is required for stockable products. If the product is not stockable, you can leave it empty."
                    )
                )

    def _get_valuation_area(self, raise_if_not_found=True):
        self.ensure_one()
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
        for line in self:
            if line.product_id:
                valuation_area = line._get_valuation_area(raise_if_not_found=False)
            else:
                valuation_area = False
            line.valuation_area_id = valuation_area
