import json

from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductCategory(models.Model):
    _inherit = "product.category"

    def _valuation_guard_misaligned(self, company=None):
        """Categories whose cost method or valuation differ from the ones of the company.

        Both fields are company dependent, so the comparison is made in the given company.
        """
        company = company or self.env.company
        categories = self.with_company(company)
        return categories.filtered(
            lambda c: c.property_cost_method != company.cost_method
            or c.property_valuation != company.inventory_valuation
        )

    @api.model
    def _valuation_guard_all_misaligned(self, company=None):
        # every category of the database: the table is small and the check must see all of them
        return self.search([])._valuation_guard_misaligned(company)  # pylint: disable=no-search-all

    def _valuation_guard_check_method(self):
        company = self.env.company
        if not company.valuation_guard_unique_method:
            return
        misaligned = self._valuation_guard_misaligned(company)
        if misaligned:
            methods = dict(self._fields["property_cost_method"]._description_selection(self.env))
            valuations = dict(self._fields["property_valuation"]._description_selection(self.env))
            raise UserError(
                self.env._(
                    "The company %(company)s uses one cost method for every product category: "
                    "%(method)s, %(valuation)s.\nThese categories differ: %(categories)s.",
                    company=company.name,
                    method=methods.get(company.cost_method),
                    valuation=valuations.get(company.inventory_valuation),
                    categories=", ".join(misaligned.mapped("complete_name")),
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        categories = super().create(vals_list)
        categories._valuation_guard_check_method()
        return categories

    def write(self, vals):
        res = super().write(vals)
        if {"property_cost_method", "property_valuation"} & set(vals):
            self._valuation_guard_check_method()
        return res

    @api.model
    def action_valuation_guard_align(self):
        """Put every category of the current company on the cost method and valuation of the company.

        Odoo recomputes the cost of the products of a category whose cost method changes, so the
        current costs are saved first, in a JSON attachment on the company, to allow a targeted
        revert of a product cost.
        """
        company = self.env.company
        misaligned = self._valuation_guard_all_misaligned(company)
        if not misaligned:
            raise UserError(self.env._("Every product category already uses the cost method of the company."))
        products = self.env["product.product"].with_company(company).search([("categ_id", "in", misaligned.ids)])
        snapshot = {
            "company_id": company.id,
            "date": fields.Datetime.to_string(fields.Datetime.now()),
            "categories": {
                c.id: [c.complete_name, c.property_cost_method, c.property_valuation]
                for c in misaligned.with_company(company)
            },
            "standard_price": {p.id: p.standard_price for p in products},
        }
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"valuation_guard_snapshot_{snapshot['date'].replace(' ', '_')}.json",
                "res_model": "res.company",
                "res_id": company.id,
                "mimetype": "application/json",
                "raw": json.dumps(snapshot, indent=1).encode(),
            }
        )
        misaligned.with_company(company).write(
            {"property_cost_method": company.cost_method, "property_valuation": company.inventory_valuation}
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": True,
                "title": self.env._("Categories aligned"),
                "message": self.env._(
                    "%(categories)s categories now use the cost method of the company. "
                    "The previous costs of %(products)s products are saved in the attachment %(file)s.",
                    categories=len(misaligned),
                    products=len(products),
                    file=attachment.name,
                ),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
