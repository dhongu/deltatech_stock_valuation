# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    valuation_class_id = fields.Many2one(
        "product.valuation.class",
        string="Valuation Class",
        company_dependent=True,
        help="Used for the products of this category that have no valuation class of their own. "
        "If the category has none, the class of the nearest parent category is used.",
    )

    def _get_valuation_class(self):
        """Clasa de evaluare a categoriei; dacă nu are, cea a celui mai apropiat părinte."""
        category = self[:1]
        while category:
            if category.valuation_class_id:
                return category.valuation_class_id
            category = category.parent_id
        return self.env["product.valuation.class"]
