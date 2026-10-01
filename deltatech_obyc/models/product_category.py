# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    valuation_class_id = fields.Many2one(
        "product.valuation.class",
        string="Valuation Class",
        company_dependent=True,
        help="Used for the products of this category that have no valuation class of their own.",
    )
