# © 2025 Deltatech
# See README.rst file on addons root folder for license details

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_valuation_class(self):
        return self.product_tmpl_id._get_valuation_class()
