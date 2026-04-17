# Copyright (C) 2024 Deltatech
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import json
import logging

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class StockTestRun(models.Model):
    _name = "stock.test.run"
    _description = "Stock Test Run"
    _order = "id desc"

    scenario_id = fields.Many2one("stock.test.scenario", string="Scenario", required=True, ondelete="cascade")
    name = fields.Char(related="scenario_id.name", store=True)
    mode = fields.Selection(
        [
            ("demo", "Generate Demo Data"),
            ("test", "Run and Validate"),
        ],
        default="test",
        required=True,
    )
    state = fields.Selection(
        [("running", "Running"), ("passed", "Passed"), ("failed", "Failed")],
        default="running",
    )
    log = fields.Text(string="Execution Log", readonly=True)
    validation_result = fields.Text(string="Validation Result", readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    log_ids = fields.One2many("stock.test.log", "run_id", string="Step Logs", readonly=True)

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    def _load_base_data(self):
        """Load and execute 00_base_data.json to populate shared records. Returns records dict."""
        base_path = file_path("deltatech_stock_test/data/scenarios/00_base_data.json", filter_ext=(".json",))
        with open(base_path, "r", encoding="utf-8") as f:
            base_data = json.load(f)
        records = {}
        for step in base_data.get("lines", []):
            step = dict(step)
            step_type = step.get("step") or step.get("type")
            method_name = "_run_step_%s" % step_type.replace("-", "_")
            if hasattr(self, method_name):
                result = getattr(self, method_name)(step, records)
                if isinstance(result, dict):
                    records.update(result)
        _logger.info("Base data loaded: %d records", len(records))
        return records

    def _add_log(self, records, step_index, step_type, state, message, document=None):
        """Create a stock.test.log entry for this run."""
        vals = {
            "run_id": self.id,
            "step_index": step_index,
            "step_type": step_type,
            "state": state,
            "message": message,
        }
        if document is not None:
            vals["document_model"] = document._name
            vals["document_id"] = document.id
            vals["document_name"] = document.display_name
        self.env["stock.test.log"].create(vals)

    def execute(self, scenario):
        """Execute a scenario dict. Called from stock.test.scenario.action_execute."""
        self.ensure_one()
        log_lines = []

        # Remove old log entries for this run (re-run case)
        self.log_ids.unlink()

        # Load shared base data (products, partners, categories) via scenario method
        log_lines.append("[0] Loading base data from 00_base_data.json...")
        if self.scenario_id:
            records = self.scenario_id._get_base_data_records()
        else:
            records = self._load_base_data()
        log_lines.append(f"    Base data loaded: {len(records)} records available.")
        self._add_log(records, 0, "load_base_data", "info",
                      f"Base data loaded: {len(records)} records available.")

        # Snapshot initial stock and account balances
        self._snapshot_initial_stock(records)
        self._snapshot_initial_accounts(records)
        self._add_log(records, 0, "snapshot_stock", "info", "Initial stock and account snapshot taken for test products.")

        # Log initial stock for base data products (and any declared in scenario's base_products)
        self._log_initial_stock(records, scenario)

        steps = scenario.get("lines", [])
        for idx, step in enumerate(steps):
            step = dict(step)
            step["_index"] = idx + 1
            step_type = step.get("step") or step.get("type")
            log_lines.append(f"[{idx + 1}] Running step: {step_type}")
            try:
                method_name = "_run_step_%s" % step_type.replace("-", "_")
                if hasattr(self, method_name):
                    keys_before = set(records.keys())
                    result = getattr(self, method_name)(step, records)
                    if isinstance(result, dict):
                        records.update(result)
                    # Log only newly added documents (keys added by this step), deduplicated by (model, id)
                    new_keys = set(records.keys()) - keys_before
                    step_docs = []
                    seen_docs = set()
                    for key in new_keys:
                        val = records[key]
                        if hasattr(val, '_name') and hasattr(val, 'id') and val.id:
                            doc_key = (val._name, val.id)
                            if doc_key not in seen_docs:
                                seen_docs.add(doc_key)
                                step_docs.append(val)
                    if step_docs:
                        for doc in step_docs:
                            log_lines.append(f"    -> {doc._name}: {doc.display_name}")
                            self._add_log(records, idx + 1, step_type, "ok",
                                          f"Created: {doc.display_name}", document=doc)
                    else:
                        self._add_log(records, idx + 1, step_type, "ok",
                                      "Step executed successfully.")
                    # Run inline checks if present
                    if step.get("checks"):
                        checks = step["checks"]
                        if isinstance(checks, str):
                            import ast
                            checks = ast.literal_eval(checks)
                        check_log = self._run_checks(checks, records)
                        log_lines.extend(check_log)
                        for check_line in check_log:
                            state = "error" if check_line.startswith("FAIL") else "ok"
                            self._add_log(records, idx + 1, "check", state, check_line)
                else:
                    raise UserError(self.env._("Unknown step type: %s") % step_type)
            except Exception as e:
                error_msg = str(e)
                log_lines.append(f"    ERROR: {error_msg}")
                self._add_log(records, idx + 1, step_type, "error", error_msg)
                self.write(
                    {
                        "state": "failed",
                        "log": "\n".join(log_lines),
                        "error_message": error_msg,
                    }
                )
                return False

        # Final expected_account_moves validation (legacy format)
        expected_moves = scenario.get("expected_account_moves", [])
        validation_lines = []
        validation_error = None
        if expected_moves:
            validation_lines = self._validate_expected_moves(expected_moves, records)
            fail_lines = [r for r in validation_lines if r.startswith("[FAIL]")]
            if fail_lines:
                validation_error = "\n".join(fail_lines)
            for vline in validation_lines:
                state = "error" if "[FAIL]" in vline else "ok"
                self._add_log(records, len(steps) + 1, "validate_account_moves", state, vline)

        if validation_error:
            self.write(
                {
                    "state": "failed",
                    "log": "\n".join(log_lines),
                    "validation_result": "\n".join(validation_lines),
                    "error_message": validation_error,
                }
            )
            return False

        self.write(
            {
                "state": "passed",
                "log": "\n".join(log_lines),
                "validation_result": "\n".join(validation_lines) if validation_lines else "OK",
            }
        )
        return True

    # -------------------------------------------------------------------------
    # Initial stock snapshot
    # -------------------------------------------------------------------------

    def _log_initial_stock(self, records, scenario):
        """Log initial stock quantities and values for base data products.
        Products are taken from records (keys starting with 'product_') plus any
        product codes listed in scenario['base_products'].
        """
        initial = records.get("_initial_stock", {})

        # Collect products to report: all product_* records from base data
        products_to_log = {}
        for key, val in records.items():
            if key.startswith("product_") and hasattr(val, "_name") and val._name == "product.product" and val.id:
                products_to_log[val.id] = val

        # Also add products declared explicitly in scenario's base_products list
        for prod_code in scenario.get("base_products", []):
            product = self.env["product.product"].search(
                [("default_code", "=", prod_code)], limit=1
            )
            if product:
                products_to_log[product.id] = product

        if not products_to_log:
            return

        for pid, product in products_to_log.items():
            stock_info = initial.get(pid, {})
            qty = stock_info.get("qty", 0.0)
            value = stock_info.get("value", 0.0)
            msg = f"Initial stock [{product.default_code or product.name}] {product.name}: qty={qty:.3f}, value={value:.2f}"
            self._add_log(records, 0, "initial_stock", "info", msg, document=product)

    def _snapshot_initial_stock(self, records):
        """Snapshot current stock qty and value for ALL products with stock (not just those in records).
        Stored in records['_initial_stock'] as {product_id: {'qty': float, 'value': float, 'by_location': {loc_id: {'qty', 'value'}}}}
        """
        initial = {}
        locations = self.env["stock.location"].search(
            [("usage", "in", ("internal", "transit")), ("company_id", "=", self.env.company.id)]
        )
        quants = self.env["stock.quant"].search(
            [("location_id", "in", locations.ids), ("quantity", "!=", 0)]
        )
        for quant in quants:
            pid = quant.product_id.id
            if pid not in initial:
                initial[pid] = {"qty": 0.0, "value": 0.0, "by_location": {}}
            initial[pid]["qty"] += quant.quantity
            initial[pid]["value"] += quant.value
            loc_id = quant.location_id.id
            if loc_id not in initial[pid]["by_location"]:
                initial[pid]["by_location"][loc_id] = {"qty": 0.0, "value": 0.0}
            initial[pid]["by_location"][loc_id]["qty"] += quant.quantity
            initial[pid]["by_location"][loc_id]["value"] += quant.value
        records["_initial_stock"] = initial
        _logger.info("Initial stock snapshot: %d products with stock", len(initial))

    def _snapshot_initial_accounts(self, records):
        """Snapshot current balance for all accounts used in scenario checks.
        Stored in records['_initial_accounts'] as {account_code: float}
        Called lazily from _check_accounting_entries on first use.
        """
        if "_initial_accounts" in records:
            return
        initial = {}
        accounts = self.env["account.account"].search(
            [("company_ids", "in", self.env.company.id)]
        )
        for account in accounts:
            lines = self.env["account.move.line"].search(
                [
                    ("account_id", "=", account.id),
                    ("company_id", "=", self.env.company.id),
                    ("parent_state", "=", "posted"),
                ]
            )
            balance = sum(lines.mapped("balance"))
            if balance != 0.0:
                initial[account.code] = balance
        records["_initial_accounts"] = initial
        # Also snapshot max account.move id to filter legacy checks
        max_move = self.env["account.move"].search(
            [("company_id", "=", self.env.company.id)], order="id desc", limit=1
        )
        records["_initial_max_move_id"] = max_move.id if max_move else 0

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------

    def _run_checks(self, checks, records):
        log_lines = []
        if "account" in checks:
            log_lines.append("  Checking accounting entries...")
            account_lines = self._check_accounting_entries(checks["account"], records)
            log_lines.extend(account_lines)
            log_lines.append("  Accounting checks passed.")
        if "stock" in checks:
            log_lines.append("  Checking stock levels...")
            stock_lines = self._check_stock_levels(checks["stock"], records)
            log_lines.extend(stock_lines)
            log_lines.append("  Stock checks passed.")
        return log_lines

    def _check_accounting_entries(self, checks, records=None):
        """
        checks: dict {account_code: expected_balance}
        Verifies the delta balance (current - initial) of posted account.move.line per account code.
        """
        log_lines = []
        for account_code, expected_balance in checks.items():
            account = self.env["account.account"].search(
                [
                    ("code", "=", str(account_code)),
                    ("company_ids", "in", self.env.company.id),
                ],
                limit=1,
            )
            if not account:
                raise AssertionError(
                    self.env._("Account with code %s not found") % account_code
                )
            lines = self.env["account.move.line"].search(
                [
                    ("account_id", "=", account.id),
                    ("company_id", "=", self.env.company.id),
                    ("parent_state", "=", "posted"),
                ]
            )
            if not lines and float(expected_balance) != 0.0:
                raise AssertionError(
                    self.env._("No posted entries found for account %s") % account_code
                )
            balance = sum(lines.mapped("balance"))
            # Subtract initial balance to get only the delta from this scenario
            initial_balance = 0.0
            if records is not None:
                initial_balance = records.get("_initial_accounts", {}).get(str(account_code), 0.0)
            delta_balance = balance - initial_balance
            log_lines.append(
                f"  CHECK Account {account_code}: balance={balance:.2f} (delta={delta_balance:.2f}, expected={expected_balance}, initial={initial_balance:.2f})"
            )
            _logger.info(
                "Account %s: expected delta=%s, initial=%.2f, current=%.2f, delta=%.2f",
                account_code,
                expected_balance,
                initial_balance,
                balance,
                delta_balance,
            )
            if (
                float_compare(delta_balance, float(expected_balance), precision_rounding=0.01)
                != 0
            ):
                raise AssertionError(
                    self.env._(
                        "Account %(code)s balance delta expected %(expected)s, got %(actual).2f (initial=%(initial).2f)"
                    ) % {"code": account_code, "expected": expected_balance, "actual": delta_balance, "initial": initial_balance}
                )
        return log_lines

    def _check_stock_levels(self, checks, records):
        """
        checks: dict {product_key: [{location_key, qty, value}]}
        product_key can be a records key (e.g. 'product_STOCK-001') or a product default_code.
        location_key can be 'incoming', 'outgoing', or a location name/usage.
        """
        log_lines = []
        for product_key, check_list in checks.items():
            # Resolve product
            product = records.get(product_key)
            if not product:
                product = self.env["product.product"].search(
                    [("default_code", "=", product_key)], limit=1
                )
            if not product:
                raise AssertionError(
                    self.env._("Product not found for key: %s") % product_key
                )

            for vals in check_list:
                location_key = vals.get("location")
                if location_key:
                    location = self.env["stock.location"].search(
                        [("complete_name", "ilike", location_key), ("usage", "=", "internal")],
                        limit=1,
                    )
                    if not location:
                        raise AssertionError(
                            self.env._("Location not found: %s") % location_key
                        )
                    quant_domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "=", location.id),
                    ]
                else:
                    locations = self.env["stock.location"].search(
                        [
                            ("usage", "in", ("internal", "transit")),
                            ("company_id", "=", self.env.company.id),
                        ]
                    )
                    quant_domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "in", locations.ids),
                    ]

                quants = self.env["stock.quant"].search(quant_domain)
                total_qty = sum(quants.mapped("quantity"))
                total_value = sum(quants.mapped("value"))

                # Subtract initial stock snapshot to get only the delta
                initial_stock = records.get("_initial_stock", {})
                initial = initial_stock.get(product.id, {})
                if location_key and location:
                    loc_initial = initial.get("by_location", {}).get(location.id, {})
                    initial_qty = loc_initial.get("qty", 0.0)
                    initial_value = loc_initial.get("value", 0.0)
                else:
                    initial_qty = initial.get("qty", 0.0)
                    initial_value = initial.get("value", 0.0)
                delta_qty = total_qty - initial_qty
                delta_value = total_value - initial_value

                log_lines.append(
                    f"  CHECK Stock [{product.default_code or product.name}] {product.name} @ {location_key or 'all'}: "
                    f"qty={total_qty:.3f} (delta={delta_qty:.3f}, expected={vals.get('qty', '-')}), "
                    f"value={total_value:.2f} (delta={delta_value:.2f}, expected={vals.get('value', '-')})"
                )
                _logger.info(
                    "Stock %s @ %s: qty=%.2f (expected %s), value=%.2f (expected %s)",
                    product.display_name,
                    location_key or "all",
                    total_qty,
                    vals.get("qty"),
                    total_value,
                    vals.get("value"),
                )

                if vals.get("qty") is not None:
                    if (
                        float_compare(
                            delta_qty, float(vals["qty"]), precision_rounding=0.001
                        )
                        != 0
                    ):
                        raise AssertionError(
                            self.env._(
                                "Stock qty for %(product)s @ %(location)s: expected %(expected)s, got %(actual).3f (current=%(current).3f, initial=%(initial).3f)"
                            ) % {
                                "product": product.display_name,
                                "location": location_key or "all",
                                "expected": vals["qty"],
                                "actual": delta_qty,
                                "current": total_qty,
                                "initial": initial_qty,
                            }
                        )
                if vals.get("value") is not None:
                    if (
                        float_compare(
                            delta_value, float(vals["value"]), precision_rounding=0.01
                        )
                        != 0
                    ):
                        raise AssertionError(
                            self.env._(
                                "Stock value for %(product)s @ %(location)s: expected %(expected)s, got %(actual).2f (current=%(current).2f, initial=%(initial).2f)"
                            ) % {
                                "product": product.display_name,
                                "location": location_key or "all",
                                "expected": vals["value"],
                                "actual": delta_value,
                                "current": total_value,
                                "initial": initial_value,
                            }
                        )
        return log_lines

    # -------------------------------------------------------------------------
    # Step handlers — setup
    # -------------------------------------------------------------------------

    def _run_step_create_account(self, step, records):
        Account = self.env["account.account"]
        existing = Account.search(
            [("code", "=", step["code"]), ("company_ids", "in", self.env.company.id)],
            limit=1,
        )
        if existing:
            key = "account_%s" % step["code"]
            return {key: existing}
        account = Account.create(
            {
                "code": step["code"],
                "name": step.get("name", step["code"]),
                "account_type": step.get("account_type", "asset_current"),
            }
        )
        key = "account_%s" % step["code"]
        return {key: account}

    def _run_step_create_partner(self, step, records):
        Partner = self.env["res.partner"]
        ref = step.get("ref")
        existing = Partner.search([("name", "=", step["name"])], limit=1)
        if existing:
            result = {"partner_%s" % step["name"].replace(" ", "_"): existing}
            if ref:
                result["partner_%s" % ref] = existing
            return result
        vals = {
            "name": step["name"],
            "customer_rank": step.get("customer_rank", 0),
            "supplier_rank": step.get("supplier_rank", 0),
            "company_type": step.get("company_type", "company"),
        }
        if ref:
            vals["ref"] = ref
        partner = Partner.create(vals)
        result = {"partner_%s" % step["name"].replace(" ", "_"): partner}
        if ref:
            result["partner_%s" % ref] = partner
        return result

    def _run_step_create_product_category(self, step, records):
        Categ = self.env["product.category"]
        name = step["name"]
        existing = Categ.search([("name", "=", name)], limit=1)
        if existing:
            update_vals = {}
            if step.get("property_cost_method"):
                update_vals["property_cost_method"] = step["property_cost_method"]
            if step.get("property_valuation"):
                update_vals["property_valuation"] = step["property_valuation"]
            if update_vals:
                existing.write(update_vals)
            key = "categ_%s" % name.replace(" ", "_")
            return {key: existing}
        vals = {"name": name}
        if step.get("property_cost_method"):
            vals["property_cost_method"] = step["property_cost_method"]
        if step.get("property_valuation"):
            vals["property_valuation"] = step["property_valuation"]
        if step.get("parent_id"):
            parent = Categ.search([("name", "=", step["parent_id"])], limit=1)
            if parent:
                vals["parent_id"] = parent.id
        categ = Categ.create(vals)
        key = "categ_%s" % name.replace(" ", "_")
        return {key: categ}

    def _run_step_create_product(self, step, records):
        Product = self.env["product.product"]
        code = step.get("code", "")
        existing = Product.search([("default_code", "=", code)], limit=1) if code else Product
        if existing and code:
            key = "product_%s" % code
            return {key: existing}

        categ_key = step.get("categ_key")
        categ = records.get(categ_key) if categ_key else None
        if not categ and step.get("categ_name"):
            categ = self.env["product.category"].search(
                [("name", "=", step["categ_name"])], limit=1
            )

        vals = {
            "name": step["name"],
            "default_code": code,
            "standard_price": step.get("standard_price", 0.0),
            "list_price": step.get("list_price", 0.0),
            "type": step.get("type", "consu"),
        }
        if step.get("is_storable"):
            vals["is_storable"] = True
        if categ:
            vals["categ_id"] = categ.id

        # Optional account overrides
        for field in ("property_account_income_id", "property_account_expense_id"):
            if step.get(field):
                acc = self.env["account.account"].search(
                    [("code", "=", step[field]), ("company_ids", "in", self.env.company.id)],
                    limit=1,
                )
                if acc:
                    vals[field] = acc.id

        product = Product.create(vals)
        key = "product_%s" % code if code else "product_%s" % step["name"].replace(" ", "_")
        return {key: product}

    # -------------------------------------------------------------------------
    # Step handlers — purchase
    # -------------------------------------------------------------------------

    def _run_step_create_purchase_order(self, step, records):
        """Create and confirm a purchase order only (no receive, no invoice)."""
        partner = self._resolve_partner(step, records)

        if "products" in step:
            product_lines = step["products"]
        else:
            product_lines = [
                {
                    "product": step.get("product"),
                    "qty": step.get("qty", 1.0),
                    "price": step.get("price", 0.0),
                }
            ]

        order_lines = []
        for line in product_lines:
            line_step = dict(step)
            line_step["product_code"] = line.get("product_code") or line.get("product")
            prod = self._resolve_product(line_step, records)
            qty = float(line.get("qty", 1.0))
            price = float(line.get("price", 0.0))
            order_lines.append((0, 0, {"product_id": prod.id, "product_qty": qty, "price_unit": price}))

        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        po_vals = {
            "partner_id": partner.id,
            "currency_id": self.env.company.currency_id.id,
            "order_line": order_lines,
        }
        if warehouse:
            po_vals["picking_type_id"] = warehouse.in_type_id.id

        po = self.env["purchase.order"].create(po_vals)
        po.button_confirm()
        idx = step.get("_index", 0)
        records[f"purchase_order_{idx}"] = po
        records["last_purchase_order"] = po
        # Save notice flag for use in receive_stock
        records["last_po_notice"] = bool(step.get("notice", False))
        return records

    def _run_step_receive_stock(self, step, records):
        """Receive goods on the last purchase order picking.

        Optional fields:
        - ``product`` / ``product_code``: receive a single product move.
        - ``products``: list of ``{product, qty}`` dicts to receive multiple lines.
        - ``qty``: quantity to receive (single-product mode); defaults to ordered qty.
        """
        po = records.get("last_purchase_order")
        if not po:
            raise UserError(self.env._("No purchase order found to receive stock for."))
        idx = step.get("_index", 0)
        picking = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))[:1]
        if picking:
            if "products" in step:
                # Multi-product receive
                for line in step["products"]:
                    product_code = line.get("product_code") or line.get("product")
                    product = self._resolve_product({"product_code": product_code}, records)
                    moves = picking.move_ids.filtered(lambda m: m.product_id.id == product.id)
                    for move in moves:
                        done_qty = float(line["qty"]) if "qty" in line else move.product_qty
                        move._set_quantity_done(done_qty)
                        move.picked = True
            else:
                qty = step.get("qty")
                product_code = step.get("product_code") or step.get("product")
                if product_code:
                    product = self._resolve_product({"product_code": product_code}, records)
                    moves = picking.move_ids.filtered(lambda m: m.product_id.id == product.id)
                else:
                    moves = picking.move_ids
                for move in moves:
                    done_qty = float(qty) if qty else move.product_qty
                    move._set_quantity_done(done_qty)
                    move.picked = True
            # Set l10n_ro_notice from purchase order step if applicable
            notice = step.get("notice", records.get("last_po_notice", False))
            if notice and hasattr(picking, "l10n_ro_notice"):
                picking.l10n_ro_notice = True
            # Only validate if all moves are picked
            if all(m.picked for m in picking.move_ids):
                picking._action_done()
            records[f"receipt_{idx}"] = picking
            records["last_receipt"] = picking
        return records

    def _run_step_return_stock(self, step, records):
        """Create a return (reverse) picking for the last receipt.

        Optional fields:
        - ``qty``: quantity to return (positive); defaults to all received qty.
        - ``product`` / ``product_code``: return a single product.
        """
        picking = records.get("last_receipt")
        if not picking:
            raise UserError(self.env._("No receipt found to return stock for."))
        idx = step.get("_index", 0)

        # Use stock.return.picking wizard logic directly
        return_moves = []
        qty = step.get("qty")
        product_code = step.get("product_code") or step.get("product")
        product = None
        if product_code:
            product = self._resolve_product({"product_code": product_code}, records)

        for move in picking.move_ids.filtered(lambda m: m.state == "done"):
            if product and move.product_id.id != product.id:
                continue
            return_qty = float(qty) if qty is not None else move.quantity_done
            return_moves.append((move, return_qty))

        if not return_moves:
            raise UserError(self.env._("No done moves found to return."))

        # Build return picking manually
        return_picking_type = picking.picking_type_id.return_picking_type_id or picking.picking_type_id
        return_picking = self.env["stock.picking"].create(
            {
                "picking_type_id": return_picking_type.id,
                "location_id": picking.location_dest_id.id,
                "location_dest_id": picking.location_id.id,
                "origin": "Return of %s" % picking.name,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": move.product_id.id,
                            "product_uom": move.product_uom.id,
                            "product_uom_qty": return_qty,
                            "location_id": picking.location_dest_id.id,
                            "location_dest_id": picking.location_id.id,
                            "origin_returned_move_id": move.id,
                        },
                    )
                    for move, return_qty in return_moves
                ],
            }
        )
        return_picking.action_confirm()
        return_picking.action_assign()
        for move in return_picking.move_ids:
            move._set_quantity_done(move.product_uom_qty)
            move.picked = True
        return_picking._action_done()

        records[f"return_{idx}"] = return_picking
        records["last_return"] = return_picking
        return records

    def _run_step_create_vendor_bill(self, step, records):
        """Create and post a vendor bill on the last purchase order.

        Optional fields:
        - ``qty`` / ``price``: override quantity/price for single-line bills.
        - ``products``: list of ``{product, qty, price}`` dicts to override specific lines.

        If ``qty`` is negative, a credit note (in_refund) is created instead of a vendor bill.
        """
        po = records.get("last_purchase_order")
        if not po:
            raise UserError(self.env._("No purchase order found to create vendor bill for."))
        idx = step.get("_index", 0)

        # Detect if this should be a credit note (qty < 0)
        qty_raw = step.get("qty")
        is_credit_note = qty_raw is not None and float(qty_raw) < 0

        if is_credit_note:
            # Create credit note directly
            price = step.get("price", 0.0)
            abs_qty = abs(float(qty_raw))
            # Resolve product: use last bill's lines or PO lines
            last_bill = records.get("last_vendor_bill")
            if last_bill:
                source_lines = last_bill.invoice_line_ids
            else:
                po.action_create_invoice()
                draft_inv = po.invoice_ids.filtered(lambda i: i.state == "draft")[:1]
                source_lines = draft_inv.invoice_line_ids if draft_inv else self.env["account.move.line"]
                if draft_inv:
                    draft_inv.button_cancel()
                    draft_inv.unlink()

            line_vals = []
            for src in source_lines:
                line_vals.append((0, 0, {
                    "product_id": src.product_id.id,
                    "quantity": abs_qty,
                    "price_unit": float(price) if price else src.price_unit,
                    "account_id": src.account_id.id,
                    "name": src.name,
                }))

            if not line_vals and po.order_line:
                for ol in po.order_line:
                    line_vals.append((0, 0, {
                        "product_id": ol.product_id.id,
                        "quantity": abs_qty,
                        "price_unit": float(price) if price else ol.price_unit,
                        "name": ol.name,
                    }))

            credit_note = self.env["account.move"].create({
                "move_type": "in_refund",
                "partner_id": po.partner_id.id,
                "invoice_date": fields.Date.context_today(self),
                "currency_id": po.currency_id.id,
                "invoice_line_ids": line_vals,
            })
            credit_note.action_post()
            records[f"vendor_bill_{idx}"] = credit_note
            records["last_vendor_bill"] = credit_note
            return records

        # Normal vendor bill
        po.action_create_invoice()
        invoice = po.invoice_ids.filtered(lambda i: i.state == "draft")[:1]
        if not invoice:
            invoice = po.invoice_ids[:1]
        if invoice:
            if "products" in step:
                # Multi-product override: match lines by product
                for line_spec in step["products"]:
                    product_code = line_spec.get("product_code") or line_spec.get("product")
                    product = self._resolve_product({"product_code": product_code}, records)
                    for inv_line in invoice.invoice_line_ids.filtered(
                        lambda l: l.product_id.id == product.id
                    ):
                        if "qty" in line_spec:
                            inv_line.quantity = float(line_spec["qty"])
                        if "price" in line_spec:
                            inv_line.price_unit = float(line_spec["price"])
            else:
                qty = step.get("qty")
                price = step.get("price")
                if qty is not None or price is not None:
                    for line in invoice.invoice_line_ids:
                        if qty is not None:
                            line.quantity = float(qty)
                        if price is not None:
                            line.price_unit = float(price)
            if not invoice.invoice_date:
                invoice.invoice_date = fields.Date.context_today(self)
            invoice.action_post()
            records[f"vendor_bill_{idx}"] = invoice
            records["last_vendor_bill"] = invoice
        return records

    def _run_step_purchase(self, step, records):
        """Create and confirm a purchase order, receive goods, create and post vendor bill."""
        partner = self._resolve_partner(step, records)

        # Support both single-product format and multi-product "products" list
        if "products" in step:
            product_lines = step["products"]
        else:
            product_lines = [
                {
                    "product": step.get("product"),
                    "qty": step.get("qty", 1.0),
                    "price": step.get("price", 0.0),
                    "inv_qty": step.get("inv_qty"),
                    "inv_price": step.get("inv_price"),
                }
            ]

        order_lines = []
        for line in product_lines:
            line_step = dict(step)
            line_step["product_code"] = line.get("product_code") or line.get("product")
            prod = self._resolve_product(line_step, records)
            qty = float(line.get("qty", 1.0))
            price = float(line.get("price", 0.0))
            order_lines.append((0, 0, {"product_id": prod.id, "product_qty": qty, "price_unit": price}))

        # Use qty/price from first line for invoice defaults (single-product compat)
        first_line = product_lines[0]
        qty = float(first_line.get("qty", 1.0))
        price = float(first_line.get("price", 0.0))
        inv_qty = float(first_line.get("inv_qty") or step.get("inv_qty") or qty)
        inv_price = float(first_line.get("inv_price") or step.get("inv_price") or price)

        # Create PO
        po = self.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "currency_id": self.env.company.currency_id.id,
                "order_line": order_lines,
            }
        )
        po.button_confirm()
        idx = step.get("_index", 0)
        records[f"purchase_order_{idx}"] = po

        # Receive — set done qty per move matching each product line
        picking = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))[:1]
        if picking:
            for move in picking.move_ids:
                move._set_quantity_done(move.product_qty)
                move.picked = True
            picking._action_done()
            records[f"receipt_{idx}"] = picking

        # Invoice
        po.action_create_invoice()
        invoice = po.invoice_ids[:1]
        if invoice:
            # For single-product format with explicit inv_qty/inv_price, override line values
            if "products" not in step and (inv_qty != qty or inv_price != price):
                for line in invoice.invoice_line_ids:
                    line.write({"quantity": inv_qty, "price_unit": inv_price})
            if not invoice.invoice_date:
                invoice.invoice_date = fields.Date.context_today(self)
            invoice.action_post()
            records[f"vendor_bill_{idx}"] = invoice

        return records

    # -------------------------------------------------------------------------
    # Step handlers — sale
    # -------------------------------------------------------------------------

    def _run_step_sale(self, step, records):
        """Create and confirm a sale order, deliver goods, create and post customer invoice.

        Supports both single-product and multi-product (``products`` list) formats.
        """
        partner = self._resolve_partner(step, records)

        if "products" in step:
            product_lines = step["products"]
        else:
            product_lines = [
                {
                    "product": step.get("product"),
                    "qty": step.get("qty", 1.0),
                    "price": step.get("price", 0.0),
                    "inv_qty": step.get("inv_qty"),
                    "inv_price": step.get("inv_price"),
                }
            ]

        order_lines = []
        for line in product_lines:
            line_step = {"product_code": line.get("product_code") or line.get("product")}
            prod = self._resolve_product(line_step, records)
            qty = float(line.get("qty", 1.0))
            price = float(line.get("price", 0.0))
            order_lines.append((0, 0, {"product_id": prod.id, "product_uom_qty": qty, "price_unit": price}))

        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "currency_id": self.env.company.currency_id.id,
                "order_line": order_lines,
            }
        )
        so.action_confirm()
        idx = step.get("_index", 0)
        records[f"sale_order_{idx}"] = so
        records["last_sale_order"] = so

        # Deliver
        picking = so.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))[:1]
        if picking:
            for move in picking.move_ids:
                move._set_quantity_done(move.product_uom_qty)
                move.picked = True
            picking._action_done()
            records[f"delivery_{idx}"] = picking
            records["last_delivery"] = picking

        # Invoice — use inv_qty/inv_price overrides per line if specified
        so._create_invoices()
        invoice = so.invoice_ids[:1]
        if invoice:
            if "products" not in step:
                # Single-product: apply inv_qty/inv_price if different
                first = product_lines[0]
                inv_qty = first.get("inv_qty")
                inv_price = first.get("inv_price")
                if inv_qty is not None or inv_price is not None:
                    for line in invoice.invoice_line_ids:
                        if inv_qty is not None:
                            line.quantity = float(inv_qty)
                        if inv_price is not None:
                            line.price_unit = float(inv_price)
            else:
                # Multi-product: match by product and apply overrides
                for line_spec in product_lines:
                    inv_qty = line_spec.get("inv_qty")
                    inv_price = line_spec.get("inv_price")
                    if inv_qty is not None or inv_price is not None:
                        product_code = line_spec.get("product_code") or line_spec.get("product")
                        prod = self._resolve_product({"product_code": product_code}, records)
                        for inv_line in invoice.invoice_line_ids.filtered(
                            lambda l: l.product_id.id == prod.id
                        ):
                            if inv_qty is not None:
                                inv_line.quantity = float(inv_qty)
                            if inv_price is not None:
                                inv_line.price_unit = float(inv_price)
            if not invoice.invoice_date:
                invoice.invoice_date = fields.Date.context_today(self)
            invoice.action_post()
            records[f"customer_invoice_{idx}"] = invoice
            records["last_customer_invoice"] = invoice

        return records

    # -------------------------------------------------------------------------
    # Step handlers — inventory adjustment
    # -------------------------------------------------------------------------

    def _run_step_inventory(self, step, records):
        """Set stock quantity via inventory adjustment (stock.quant)."""
        product = self._resolve_product(step, records)
        location_name = step.get("location")
        location = None
        if location_name:
            location = self.env["stock.location"].search(
                [("complete_name", "ilike", location_name), ("usage", "=", "internal")],
                limit=1,
            )
        if not location:
            location = self.env["stock.warehouse"].search(
                [("company_id", "=", self.env.company.id)], limit=1
            ).lot_stock_id

        qty = float(step.get("qty", 0.0))
        quant = self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": product.id,
                "location_id": location.id,
                "inventory_quantity": qty,
            }
        )
        quant.action_apply_inventory()
        idx = step.get("_index", 0)
        return {f"inventory_{idx}": quant}

    # -------------------------------------------------------------------------
    # Step handlers — internal transfers
    # -------------------------------------------------------------------------

    def _run_step_transfer_direct(self, step, records):
        """Direct internal transfer between two locations."""
        product = self._resolve_product(step, records)
        qty = float(step.get("qty", 1.0))

        location_src = self._resolve_location(step.get("location"), "internal")
        location_dest = self._resolve_location(step.get("location1"), "internal")

        move = self.env["stock.move"].create(
            {
                "company_id": self.env.company.id,
                "name": step.get("name", "Internal Transfer"),
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": qty,
            }
        )
        move._action_confirm()
        move._action_assign()
        move._set_quantity_done(qty)
        move.picked = True
        move._action_done()
        idx = step.get("_index", 0)
        return {f"transfer_direct_{idx}": move.picking_id}

    def _run_step_transfer_transit(self, step, records):
        """Two-step internal transfer via transit location."""
        product = self._resolve_product(step, records)
        qty = float(step.get("qty", 1.0))
        location_src = self._resolve_location(step.get("location"), "internal")

        # Find transit location
        transit_loc = self.env["stock.location"].search(
            [("usage", "=", "transit"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        if not transit_loc:
            raise UserError(self.env._("No transit location found for company."))

        # Find transit route
        transit_route = self.env["stock.route"].search(
            [("name", "ilike", "transit")], limit=1
        )

        move_vals = {
            "company_id": self.env.company.id,
            "name": step.get("name", "Transit Transfer"),
            "location_id": location_src.id,
            "location_dest_id": transit_loc.id,
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
        }
        if transit_route:
            move_vals["route_ids"] = [(4, transit_route.id)]

        move_out = self.env["stock.move"].create(move_vals)
        move_out._action_confirm()
        move_out._action_assign()
        move_out._set_quantity_done(qty)
        move_out.picked = True
        move_out._action_done()

        # Complete the inbound leg if push rules created it
        move_in = move_out.move_dest_ids
        if move_in and move_in.state == "assigned":
            move_in.picking_id.move_ids.picked = True
            move_in.picking_id.button_validate()

        idx = step.get("_index", 0)
        return {
            f"transfer_transit_out_{idx}": move_out.picking_id,
            f"transfer_transit_in_{idx}": move_in.picking_id if move_in else False,
        }

    # -------------------------------------------------------------------------
    # Step handlers — consume / usage_giving
    # -------------------------------------------------------------------------

    def _run_step_consume(self, step, records):
        return self._create_stock_picking_by_type("consume", step, records)

    def _run_step_usage_giving(self, step, records):
        return self._create_stock_picking_by_type("usage_giving", step, records)

    def _create_stock_picking_by_type(self, oper_type, step, records):
        product = self._resolve_product(step, records)
        qty = float(step.get("qty", 1.0))

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(self.env._("No outgoing picking type found."))

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": qty,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move._set_quantity_done(qty)
            move.picked = True
        picking._action_done()
        idx = step.get("_index", 0)
        return {f"{oper_type}_{idx}": picking}

    # -------------------------------------------------------------------------
    # Step handlers — invoice (legacy format)
    # -------------------------------------------------------------------------

    def _run_step_create_invoice(self, step, records):
        partner_name = step.get("partner_name") or step.get("partner")
        partner = None
        if partner_name:
            partner = self.env["res.partner"].search([("name", "=", partner_name)], limit=1)
        if not partner:
            partner_key = "partner_%s" % (partner_name or "").replace(" ", "_")
            partner = records.get(partner_key)
        if not partner:
            raise UserError(self.env._("Partner not found: %s") % partner_name)

        # Build line specs: support both legacy "invoice_lines" and new "products" list
        line_specs = step.get("products") or step.get("invoice_lines") or []
        if not line_specs:
            # single-product shorthand
            product_code = step.get("product") or step.get("product_code")
            if product_code:
                line_specs = [
                    {
                        "product_code": product_code,
                        "quantity": step.get("qty", step.get("quantity", 1)),
                        "price_unit": step.get("price", step.get("price_unit", 0.0)),
                    }
                ]

        invoice_lines = []
        for line in line_specs:
            product_code = line.get("product_code") or line.get("product")
            product = records.get("product_%s" % product_code)
            if not product:
                product = self.env["product.product"].search(
                    [("default_code", "=", product_code)], limit=1
                )
            if not product:
                raise UserError(self.env._("Product not found: %s") % product_code)
            invoice_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": line.get("quantity", line.get("qty", 1)),
                        "price_unit": line.get("price_unit", line.get("price", 0.0)),
                        "name": product.name,
                    },
                )
            )

        invoice = self.env["account.move"].create(
            {
                "move_type": step.get("move_type", "out_invoice"),
                "partner_id": partner.id,
                "invoice_line_ids": invoice_lines,
            }
        )
        key = step.get("key", "invoice_%s" % step.get("_index", 0))
        return {key: invoice}

    def _run_step_post_invoice(self, step, records):
        key = step.get("key", "invoice")
        invoice = records.get(key)
        if not invoice:
            raise UserError(self.env._("Invoice not found for key: %s") % key)
        if not invoice.invoice_date:
            invoice.invoice_date = fields.Date.context_today(self)
        invoice.action_post()
        return {}

    # -------------------------------------------------------------------------
    # Step handlers — stock picking (legacy format)
    # -------------------------------------------------------------------------

    def _run_step_create_stock_picking(self, step, records):
        picking_type_code = step.get("picking_type_code", "incoming")
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", picking_type_code),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(
                self.env._("No picking type found for code: %s") % picking_type_code
            )

        move_lines = []
        for ml in step.get("move_lines", []):
            product_code = ml.get("product_code")
            product = records.get("product_%s" % product_code)
            if not product:
                product = self.env["product.product"].search(
                    [("default_code", "=", product_code)], limit=1
                )
            if not product:
                raise UserError(self.env._("Product not found: %s") % product_code)
            move_lines.append(
                (
                    0,
                    0,
                    {
                        "name": product.name,
                        "product_id": product.id,
                        "product_uom": product.uom_id.id,
                        "product_uom_qty": ml.get("quantity", 1),
                        "location_id": picking_type.default_location_src_id.id,
                        "location_dest_id": picking_type.default_location_dest_id.id,
                    },
                )
            )

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "move_ids": move_lines,
            }
        )
        key = step.get("key", "picking_%s" % step.get("_index", 0))
        return {key: picking}

    def _run_step_validate_picking(self, step, records):
        key = step.get("key", "picking")
        picking = records.get(key)
        if not picking:
            raise UserError(self.env._("Picking not found for key: %s") % key)
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move._set_quantity_done(move.product_uom_qty)
            move.picked = True
        picking._action_done()
        return {}

    # -------------------------------------------------------------------------
    # Legacy expected_account_moves validation
    # -------------------------------------------------------------------------

    def _validate_expected_moves(self, expected_moves, records):
        results = []
        initial_accounts = records.get("_initial_accounts", {})

        for expected in expected_moves:
            journal_name = expected.get("journal")
            journal = self.env["account.journal"].search(
                [("name", "ilike", journal_name)], limit=1
            ) if journal_name else self.env["account.journal"]

            for exp_line in expected.get("line_ids", []):
                account_code = exp_line.get("account")
                if not account_code:
                    continue
                account = self.env["account.account"].search(
                    [("code", "=", str(account_code)), ("company_ids", "in", self.env.company.id)],
                    limit=1,
                )
                if not account:
                    results.append(f"WARN: Account {account_code} not found")
                    continue

                # Compute current total balance for this account (all posted lines)
                all_lines = self.env["account.move.line"].search(
                    [
                        ("account_id", "=", account.id),
                        ("company_id", "=", self.env.company.id),
                        ("parent_state", "=", "posted"),
                    ]
                )
                if journal:
                    all_lines = all_lines.filtered(lambda l: l.journal_id == journal)

                total_debit = sum(all_lines.mapped("debit"))
                total_credit = sum(all_lines.mapped("credit"))
                total_balance = sum(all_lines.mapped("balance"))

                # Subtract initial values to get delta from this scenario
                initial_balance = initial_accounts.get(str(account_code), 0.0)
                delta_balance = total_balance - initial_balance

                # Support both "balance" and "debit"/"credit" in expected line
                if "balance" in exp_line:
                    exp_balance = float(exp_line["balance"])
                    balance_ok = float_compare(delta_balance, exp_balance, precision_rounding=0.01) == 0
                    status = "OK" if balance_ok else "[FAIL]"
                    results.append(
                        f"[{status}] Account {account_code}: "
                        f"balance_delta={delta_balance:.2f} (expected {exp_balance:.2f}, initial={initial_balance:.2f})"
                    )
                else:
                    # Legacy debit/credit check using delta from new moves only
                    new_moves_domain = [
                        ("state", "=", "posted"),
                        ("company_id", "=", self.env.company.id),
                        ("id", ">", records.get("_initial_max_move_id", 0)),
                    ]
                    if journal:
                        new_moves_domain.append(("journal_id", "=", journal.id))
                    new_moves = self.env["account.move"].search(new_moves_domain)
                    new_lines = new_moves.line_ids.filtered(lambda l: l.account_id == account)
                    new_debit = sum(new_lines.mapped("debit"))
                    new_credit = sum(new_lines.mapped("credit"))

                    exp_debit = float(exp_line.get("debit", 0))
                    exp_credit = float(exp_line.get("credit", 0))

                    debit_ok = float_compare(new_debit, exp_debit, precision_rounding=0.01) == 0
                    credit_ok = float_compare(new_credit, exp_credit, precision_rounding=0.01) == 0

                    status = "OK" if (debit_ok and credit_ok) else "[FAIL]"
                    results.append(
                        f"[{status}] Account {account_code}: "
                        f"debit={new_debit:.2f} (expected {exp_debit:.2f}), "
                        f"credit={new_credit:.2f} (expected {exp_credit:.2f})"
                    )
        return results

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_partner(self, step, records):
        partner_name = step.get("partner_name") or step.get("partner")
        if partner_name:
            key = "partner_%s" % partner_name.replace(" ", "_")
            partner = records.get(key)
            if not partner:
                partner = self.env["res.partner"].search([("name", "=", partner_name)], limit=1)
            if partner:
                return partner
        raise UserError(self.env._("Partner not found: %s") % partner_name)

    def _resolve_product(self, step, records):
        product_code = step.get("product_code") or step.get("code")
        if product_code:
            key = "product_%s" % product_code
            product = records.get(key)
            if not product:
                product = self.env["product.product"].search(
                    [("default_code", "=", product_code)], limit=1
                )
            if product:
                return product
        product_name = step.get("product_name") or step.get("name")
        if product_name:
            product = self.env["product.product"].search([("name", "=", product_name)], limit=1)
            if product:
                return product
        raise UserError(self.env._("Product not found for step: %s") % json.dumps(step))

    def _resolve_location(self, location_name, usage="internal"):
        if not location_name:
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.env.company.id)], limit=1
            )
            return warehouse.lot_stock_id
        location = self.env["stock.location"].search(
            [("complete_name", "ilike", location_name), ("usage", "=", usage)],
            limit=1,
        )
        if not location:
            raise UserError(self.env._("Location not found: %s") % location_name)
        return location
