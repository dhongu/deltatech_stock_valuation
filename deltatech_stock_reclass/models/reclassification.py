# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from .stock_move import SKIP_ENTRY_CONTEXT_KEY


class StockReclassification(models.Model):
    _name = "stock.reclassification"
    _description = "Stock Reclassification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="/", copy=False, readonly=True)
    state = fields.Selection(
        selection=[("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")],
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    date = fields.Date(required=True, default=fields.Date.context_today, copy=False)
    rule_id = fields.Many2one(
        "stock.reclassification.rule",
        string="Rule",
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    account_src_id = fields.Many2one(related="rule_id.account_src_id", string="Source Account")
    account_dest_id = fields.Many2one(related="rule_id.account_dest_id", string="Destination Account")
    destination_type = fields.Selection(related="rule_id.destination_type")
    require_decision = fields.Boolean(related="rule_id.require_decision")
    require_reason = fields.Boolean(related="rule_id.require_reason")
    location_src_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        required=True,
        check_company=True,
        domain="[('usage', '=', 'internal')]",
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        required=True,
        check_company=True,
        domain="[('usage', 'not in', ('supplier', 'customer', 'view'))]",
    )
    decision_note = fields.Text(
        string="Management Decision",
        help="Reference of the written decision that changes the destination of the goods.",
    )
    reason = fields.Text()
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env.company.account_stock_journal_id,
    )
    line_ids = fields.One2many("stock.reclassification.line", "reclassification_id", string="Products", copy=True)
    picking_id = fields.Many2one("stock.picking", string="Transfer", copy=False, readonly=True, check_company=True)
    reverse_picking_id = fields.Many2one(
        "stock.picking", string="Reverse Transfer", copy=False, readonly=True, check_company=True
    )
    account_move_id = fields.Many2one(
        "account.move", string="Journal Entry", copy=False, readonly=True, check_company=True
    )
    reverse_account_move_id = fields.Many2one(
        "account.move", string="Reversal Entry", copy=False, readonly=True, check_company=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("stock.reclassification") or "/"
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done(self):
        if any(rec.state == "done" for rec in self):
            raise UserError(self.env._("A validated reclassification cannot be deleted: cancel it instead."))

    # ------------------------------------------------------------------ checks

    def _check_before_validate(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(self.env._("Only a draft reclassification can be validated."))
        if not self.line_ids:
            raise UserError(self.env._("Add at least one product."))
        rule = self.rule_id
        if not rule.active:
            raise UserError(self.env._("The rule %s is archived.", rule.display_name))
        if rule.require_decision and not (self.decision_note or "").strip():
            raise UserError(self.env._("The rule %s requires the management decision.", rule.display_name))
        if rule.require_reason and not (self.reason or "").strip():
            raise UserError(self.env._("The rule %s requires the reason.", rule.display_name))
        self.line_ids._check_before_validate()

    def _check_before_cancel(self):
        """Hook: an extension can refuse the cancellation (e.g. assets already validated)."""
        self.ensure_one()

    def _post_validate(self):
        """Hook: called after the transfer is done and the journal entry posted."""
        self.ensure_one()

    # --------------------------------------------------------------- transfer

    def _get_picking_type(self, location):
        self.ensure_one()
        domain = [("code", "=", "internal"), ("company_id", "=", self.company_id.id)]
        # the internal type is archived while the multi-location option is off: still usable here
        picking_type = self.env["stock.picking.type"].with_context(active_test=False)
        warehouse = location.warehouse_id
        if warehouse and warehouse.int_type_id:
            return warehouse.int_type_id
        if warehouse:
            picking_type = picking_type.search(domain + [("warehouse_id", "=", warehouse.id)], limit=1)
        if not picking_type:
            picking_type = picking_type.search(domain, limit=1)
        if not picking_type:
            raise UserError(self.env._("No internal operation type found for the company %s.", self.company_id.name))
        return picking_type

    def _create_transfer(self, location_src, location_dest, origin):
        """Create, reserve and validate an internal transfer for the lines of the document.
        Its moves do not post the automatic valuation entry (the document posts its own)."""
        self.ensure_one()
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self._get_picking_type(location_src).id,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
                "origin": origin,
                "company_id": self.company_id.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": line.product_id.id,
                            "product_uom_qty": line.quantity,
                            "product_uom": line.product_id.uom_id.id,
                            "location_id": location_src.id,
                            "location_dest_id": location_dest.id,
                            "company_id": self.company_id.id,
                        }
                    )
                    for line in self.line_ids
                ],
            }
        )
        picking.action_confirm()
        moves = picking.move_ids.sorted("id")
        # the confirmation may already reserve (FIFO, any lot): reserve exactly what the line asks for
        moves._do_unreserve()
        for line, move in zip(self.line_ids, moves, strict=True):
            taken = move._update_reserved_quantity(line.quantity, location_src, lot_id=line.lot_id, strict=False)
            if float_compare(taken, line.quantity, precision_rounding=move.product_uom.rounding) < 0:
                raise UserError(
                    self.env._(
                        "Not enough stock of %(product)s in %(location)s: %(taken)s available, %(needed)s needed.",
                        product=line.product_id.display_name,
                        location=location_src.display_name,
                        taken=taken,
                        needed=line.quantity,
                    )
                )
        picking.move_ids.picked = True
        picking.with_context(**{SKIP_ENTRY_CONTEXT_KEY: True})._action_done()
        return picking

    # ------------------------------------------------------------ journal entry

    def _prepare_note_line_vals(self, line, account_debit, account_credit):
        label = f"{self.name} - {line.product_id.display_name}"
        return [
            Command.create(
                {
                    "account_id": account_credit.id,
                    "name": label,
                    "debit": 0.0,
                    "credit": line.value,
                    "product_id": line.product_id.id,
                }
            ),
            Command.create(
                {
                    "account_id": account_debit.id,
                    "name": label,
                    "debit": line.value,
                    "credit": 0.0,
                    "product_id": line.product_id.id,
                    "quantity": line.quantity,
                    "product_uom_id": line.product_id.uom_id.id,
                }
            ),
        ]

    def _post_note(self):
        self.ensure_one()
        line_vals = []
        for line in self.line_ids:
            if self.currency_id.is_zero(line.value):
                continue
            line_vals += self._prepare_note_line_vals(line, self.account_dest_id, self.account_src_id)
        if not line_vals:
            return self.env["account.move"]
        note = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "ref": self.name,
                    "journal_id": self.journal_id.id,
                    "date": self.date,
                    "line_ids": line_vals,
                }
            )
        )
        note._post()
        return note

    # ------------------------------------------------------------------ actions

    def action_validate(self):
        for rec in self:
            rec._check_before_validate()
            rec.picking_id = rec._create_transfer(rec.location_src_id, rec.location_dest_id, rec.name)
            rec.line_ids._set_cost_from_moves(rec.picking_id)
            rec.account_move_id = rec._post_note()
            rec.state = "done"
            rec.line_ids._warn_invoice_price()
            rec._post_validate()
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancel":
                continue
            if rec.state == "done":
                rec._check_before_cancel()
                rec.reverse_picking_id = rec._create_transfer(
                    rec.location_dest_id, rec.location_src_id, self.env._("%s (reversal)", rec.name)
                )
                if rec.account_move_id:
                    reversal = rec.account_move_id._reverse_moves(
                        [{"date": fields.Date.context_today(rec), "ref": self.env._("Reversal of %s", rec.name)}],
                        cancel=True,
                    )
                    rec.reverse_account_move_id = reversal
            rec.state = "cancel"
        return True

    def action_open_picking(self):
        self.ensure_one()
        return self._action_open_record(self.picking_id)

    def action_open_account_move(self):
        self.ensure_one()
        return self._action_open_record(self.account_move_id)

    def _action_open_record(self, record):
        if not record:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": record._name,
            "res_id": record.id,
            "view_mode": "form",
        }


class StockReclassificationLine(models.Model):
    _name = "stock.reclassification.line"
    _description = "Stock Reclassification Line"
    _check_company_auto = True

    reclassification_id = fields.Many2one("stock.reclassification", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="reclassification_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    state = fields.Selection(related="reclassification_id.state")
    product_id = fields.Many2one(
        "product.product",
        required=True,
        check_company=True,
        domain="[('is_storable', '=', True)]",
    )
    tracking = fields.Selection(related="product_id.tracking")
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial Number",
        check_company=True,
        domain="[('product_id', '=', product_id)]",
    )
    quantity = fields.Float(digits="Product Unit", required=True, default=1.0)
    product_uom_id = fields.Many2one(related="product_id.uom_id", string="Unit")
    invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Vendor Bill Line",
        check_company=True,
        domain="[('move_id.move_type', '=', 'in_invoice'), ('move_id.state', '=', 'posted'),"
        " ('display_type', '=', 'product'), ('product_id', '=', product_id)]",
        help="Optional: the vendor bill line the reclassified goods were bought with.",
    )
    unit_cost = fields.Monetary(readonly=True, copy=False)
    value = fields.Monetary(readonly=True, copy=False)

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(self.env._("The quantity must be positive."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.lot_id and self.lot_id.product_id != self.product_id:
            self.lot_id = False
        if self.invoice_line_id and self.invoice_line_id.product_id != self.product_id:
            self.invoice_line_id = False

    def _check_before_validate(self):
        for line in self:
            product = line.product_id
            if product.tracking != "none" and not line.lot_id:
                raise UserError(self.env._("Select the lot or serial number of %s.", product.display_name))
            if product.tracking == "none" and line.lot_id:
                raise UserError(self.env._("%s is not tracked: remove the lot.", product.display_name))
            if product.tracking == "serial" and float_compare(line.quantity, 1.0, precision_digits=0) != 0:
                raise UserError(self.env._("A serial number has quantity 1 (%s).", product.display_name))
            line._check_invoice_line()

    def _invoice_line_quantity(self):
        self.ensure_one()
        invoice_line = self.invoice_line_id
        return invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, self.product_id.uom_id)

    def _check_invoice_line(self):
        self.ensure_one()
        invoice_line = self.invoice_line_id
        if not invoice_line:
            return
        if invoice_line.product_id != self.product_id or invoice_line.move_id.state != "posted":
            raise UserError(self.env._("The bill line does not match the product or is not posted."))
        already = sum(
            self.search(
                [
                    ("invoice_line_id", "=", invoice_line.id),
                    ("reclassification_id.state", "=", "done"),
                    ("id", "!=", self.id),
                ]
            ).mapped("quantity")
        )
        if (
            float_compare(
                already + self.quantity,
                self._invoice_line_quantity(),
                precision_rounding=self.product_id.uom_id.rounding,
            )
            > 0
        ):
            raise UserError(
                self.env._(
                    "The reclassified quantity of %(product)s exceeds the quantity of the bill line %(bill)s.",
                    product=self.product_id.display_name,
                    bill=invoice_line.move_id.name,
                )
            )

    def _get_cost_without_move(self):
        """Current cost of the goods when the transfer does not value the move (the stock stays
        inside the company): the cost of the lot or of the product."""
        self.ensure_one()
        product = self.product_id.with_company(self.company_id)
        if product.lot_valuated and self.lot_id:
            return self.lot_id.with_company(self.company_id).standard_price
        return product.standard_price

    def _set_cost_from_moves(self, picking):
        moves = picking.move_ids.sorted("id")
        for line, move in zip(self, moves, strict=True):
            rounding = line.product_id.uom_id.rounding
            if move.is_out and not float_is_zero(move.value, precision_rounding=0.0001):
                value = move.value
            else:
                value = line._get_cost_without_move() * line.quantity
            value = line.currency_id.round(value)
            line.write(
                {
                    "value": value,
                    "unit_cost": value / line.quantity
                    if not float_is_zero(line.quantity, precision_rounding=rounding)
                    else 0.0,
                }
            )

    def _warn_invoice_price(self):
        for line in self.filtered("invoice_line_id"):
            qty = line._invoice_line_quantity()
            if not qty:
                continue
            invoice_unit = abs(line.invoice_line_id.balance) / qty
            if not line.currency_id.is_zero(invoice_unit - line.unit_cost):
                line.reclassification_id.message_post(
                    body=self.env._(
                        "%(product)s: the cost of the stock (%(cost)s) differs from the price of the bill line "
                        "%(bill)s (%(price)s).",
                        product=line.product_id.display_name,
                        cost=line.currency_id.round(line.unit_cost),
                        bill=line.invoice_line_id.move_id.name,
                        price=line.currency_id.round(invoice_unit),
                    )
                )
