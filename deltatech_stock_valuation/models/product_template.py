# ©  2023 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license detai

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_valuation_ids = fields.One2many("product.valuation", "product_tmpl_id")

    def recompute_valuation_amount(self):
        # evaluarea e date derivate, scrise doar de contabilul-șef (vezi ir.model.access.csv)
        Valuation = self.env["product.valuation"].sudo()
        valuations = Valuation
        for product in self:
            for variant in product.product_variant_ids:
                company = variant.company_id or self.env.company
                account = variant.categ_id.property_stock_valuation_account_id
                if not account:
                    continue

                if not account.is_for_stock_valuation:
                    account.is_for_stock_valuation = True

                valuation_area = company.valuation_area_id
                valuations |= Valuation.get_valuation(variant.id, valuation_area.id, account.id, company.id)

        valuations._recompute_amount()
