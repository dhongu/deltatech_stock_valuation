# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import api, fields, models
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

    # _valuation_area_id_required = models.Constraint(
    #     "CHECK(valuation_area_id IS NOT NULL OR product_id IS NULL)",
    #     "Valuation Area is required for stockable products. If the product is not stockable, you can leave it empty.",
    # )

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
                    self.env._(
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

    def _copy_data_extend_business_fields(self, values):
        """Inversarea unei note de stoc fără storno: nucleul trece suma pe partea opusă,
        dar copiază cantitatea cu același semn. Pe notele de tip entry cantitatea e
        semnată (pozitivă pe debit, negativă pe credit), deci trebuie inversată odată
        cu partea, altfel inversul unei recepții ar număra încă o intrare. Cu storno,
        linia rămâne pe aceeași parte (sumă negativă) și semnul sumei anulează intrarea,
        deci cantitatea nu se schimbă; excepție fac liniile de valoare zero (mișcări la
        cost 0), care nu au semn de sumă. Metoda e apelată de nucleu doar la inversare
        (`_reverse_moves`)."""
        res = super()._copy_data_extend_business_fields(values)
        if self.move_id.move_type == "entry" and self.product_id and self.quantity:
            storno = self.company_id.account_storno
            if not storno or self.company_currency_id.is_zero(self.balance):
                values["quantity"] = -self.quantity
        return res

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

            stock_moves = self.move_id.stock_move_ids
            if "purchase_line_id" in self._fields:
                if self.purchase_line_id:
                    stock_moves = self.purchase_line_id.move_ids
            if "sale_line_ids" in self._fields:
                if self.sale_line_ids:
                    stock_moves = self.sale_line_ids.mapped("move_ids")
            if stock_moves:
                stock_move = next(iter(stock_moves), None)
                valuation_area = stock_move._get_valuation_area(raise_if_not_found)
        if not valuation_area and raise_if_not_found:
            raise UserError(self.env._("Valuation area is not defined"))

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
