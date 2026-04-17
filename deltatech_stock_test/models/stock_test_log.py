from odoo import api, fields, models


def _get_document_selection(self):
    """Return all models that can be referenced as documents."""
    return [
        ("account.move", "Account Move"),
        ("purchase.order", "Purchase Order"),
        ("sale.order", "Sale Order"),
        ("stock.picking", "Stock Picking"),
        ("stock.move", "Stock Move"),
        ("product.product", "Product"),
    ]


class StockTestLog(models.Model):
    _name = "stock.test.log"
    _description = "Stock Test Log Entry"
    _order = "run_id, step_index"

    run_id = fields.Many2one("stock.test.run", string="Run", required=True, ondelete="cascade")
    step_index = fields.Integer(string="Step #")
    step_type = fields.Char(string="Step Type")
    state = fields.Selection(
        [
            ("info", "Info"),
            ("ok", "OK"),
            ("error", "Error"),
        ],
        default="info",
        string="State",
    )
    message = fields.Text(string="Message")
    document_model = fields.Char(string="Document Model")
    document_id = fields.Integer(string="Document ID")
    document_name = fields.Char(string="Document")
    document_ref = fields.Reference(
        selection=_get_document_selection,
        string="Document",
        compute="_compute_document_ref",
        store=False,
    )

    @api.depends("document_model", "document_id")
    def _compute_document_ref(self):
        for rec in self:
            if rec.document_model and rec.document_id:
                try:
                    rec.document_ref = "%s,%d" % (rec.document_model, rec.document_id)
                except Exception:
                    rec.document_ref = False
            else:
                rec.document_ref = False
