
## Overview

`deltatech_account_scenario` is an Odoo 19 module that provides a **JSON-driven framework** for running and validating complete accounting scenarios. It allows developers and accountants to define business processes (invoices, payments, journal entries, fixed assets, stock receipts, deliveries, etc.) as JSON scenarios, execute them against a live Odoo database, and automatically validate the resulting accounting entries and stock valuations.

The module supports two modes of operation:
- **Test mode** — executes a scenario and validates that the generated account moves and stock values match the expected entries defined in the JSON.
- **Demo mode** — executes a scenario to generate demo/sample data without strict accounting validation.

---

## Features

### JSON-Driven Scenarios
- Define complete business processes as structured JSON, including steps (actions) and expected accounting/stock entries.
- Steps are divided into two categories:
  - **Master data steps** — create or resolve reference data (accounts, partners, product categories, products).
  - **Transactional steps** — execute business operations (purchase orders, stock receipts, vendor bills, sale orders, invoices, stock pickings, journal entries, payments).
- Each step can include a `_comment` field; if present, its value is used as the log message instead of the auto-generated one.

### Accounting & Stock Validation
- After executing all steps, the runner compares the generated `account.move.line` entries against the `expected_account_moves` section of the JSON.
- Validates account codes, debit/credit amounts, and analytic accounts.
- Validates stock quantities and values per product via the `checks` section in each step.
- Reports mismatches clearly in the run log.

### UI Integration
- **Scenario list** — view and manage JSON scenarios; import JSON files via the **Import Scenarios** button (always visible, no selection required).
- **Scenario form** — view, edit, and export a scenario as JSON via the **Export JSON** button.
- **Run history** — each execution is recorded as a `account.test.run` record with full execution log and validation result.
- **Log navigation** — clicking a log line with a document reference opens the related document (invoice, picking, payment, etc.) directly.
- **Buttons** — "Set Ready", "Execute Scenario", "Re-run Scenario", "View Runs" available from the scenario form.
- Menu: **Accounting → Account Scenarios → Test Scenarios** and **Test Runs** (accessible via the Accounting main menu).

### Built-in Scenario Library
- Ships with base data (`00_base_data.json`) defining shared product categories, partners, and products used across all scenarios.
- Includes demo scenarios for purchase/sale flows, inventory transfers, stock receipts with invoices, and stock pickings.
- Includes **140 Romanian stock accounting test scenarios** under `data/scenarios/ro_stock/`:
  - **70 FIFO scenarios** (`ro_stock_fifo_case_XXXX.json`) — covering FIFO cost method edge cases per Romanian accounting regulations.
  - **70 Average cost scenarios** (`ro_stock_avg_case_XXXX.json`) — covering weighted average cost method edge cases.

### Automated Tests
- Includes `TransactionCase` tests under `tests/test_stock_scenarios.py` and `tests/common.py` covering:
  - Product category creation step
  - Partner creation step
  - Product creation step
  - Invoice creation and posting step
  - Full scenario execution
  - Purchase and sale with accounting checks
  - Error handling for unknown step types

---

## JSON Scenario Format

```json
{
  "id": "my_scenario",
  "name": "Scenario Name",
  "mode": "test",
  "currency": "RON",
  "lines": [ ... ],
  "expected_account_moves": [ ... ]
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier for the scenario |
| `name` | string | Human-readable name displayed in the UI |
| `mode` | string | `"test"` (validates accounting) or `"demo"` (no validation) |
| `currency` | string | ISO currency code (e.g. `"RON"`, `"EUR"`) |
| `lines` | array | List of steps to execute in order |
| `expected_account_moves` | array | Expected accounting entries to validate after execution |

---

## Master Data Steps

Master data steps create or resolve reference records (accounts, partners, categories, products).
They are **idempotent** — if the record already exists it is reused, not duplicated.
Typically placed in a shared `00_base_data.json` loaded before all scenarios.

---

### `create_account`

Creates a chart of accounts entry.

```json
{
  "step": "create_account",
  "code": "371",
  "name": "Marfuri",
  "account_type": "asset_current"
}
```

| Field | Required | Description |
|---|---|---|
| `code` | ✅ | Account code (e.g. `"371"`) |
| `name` | ✅ | Account name |
| `account_type` | ✅ | Odoo account type (e.g. `"asset_current"`, `"liability_payable"`) |

---

### `create_partner`

Creates or updates a customer or supplier partner. If a partner with the same `vat` or `name` already exists, it is updated with the values from the step.

```json
{
  "step": "create_partner",
  "name": "Furnizor Test SRL",
  "ref": "supplier_1",
  "vat": "RO12345678",
  "country": "RO",
  "supplier_rank": 1,
  "customer_rank": 0
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Partner name |
| `ref` | ✅ | Internal reference — used to resolve the partner in transactional steps (e.g. `"supplier_1"`) |
| `vat` | — | VAT / CIF number (e.g. `"RO12345678"`); used as primary lookup key if present |
| `country` | — | ISO country code (e.g. `"RO"`, `"DE"`); also accepted as `country_id` |
| `supplier_rank` | — | Set to `1` for suppliers |
| `customer_rank` | — | Set to `1` for customers |

---

### `create_product_category`

Creates or updates a product category with cost method, valuation properties, and accounting accounts. If a category with the same name already exists, it is updated.

```json
{
  "step": "create_product_category",
  "name": "Servicii",
  "property_cost_method": "average",
  "property_valuation": "real_time",
  "property_account_income_categ_id": "704",
  "property_account_expense_categ_id": "604",
  "property_stock_valuation_account_id": "371"
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Category name |
| `property_cost_method` | — | `"standard"`, `"average"`, or `"fifo"` (default: `"standard"`) |
| `property_valuation` | — | `"real_time"` (perpetual/automatic) or `"periodic"` (manual) |
| `property_account_income_categ_id` | — | Account code for income (e.g. `"704"`) |
| `property_account_expense_categ_id` | — | Account code for expense (e.g. `"604"`) |
| `property_stock_valuation_account_id` | — | Account code for stock valuation (e.g. `"371"`) |

The category is stored in records with key `categ_<name_normalized>` (spaces replaced by `_`).

---

### `create_product`

Creates a storable or consumable product.

```json
{
  "step": "create_product",
  "code": "PROD-AVG-001",
  "name": "Produs Medie Ponderata",
  "categ_key": "categ_RO_Stock_AVG",
  "standard_price": 100.0,
  "list_price": 150.0,
  "type": "consu"
}
```

| Field | Required | Description |
|---|---|---|
| `code` | ✅ | Internal reference / default code — used to resolve the product in transactional steps |
| `name` | ✅ | Product name |
| `categ_key` | — | Key of a previously created category (e.g. `"categ_RO_Stock_AVG"`) |
| `standard_price` | — | Cost price |
| `list_price` | — | Sales price |
| `type` | — | `"consu"` (consumable) or `"service"` (default: `"consu"`) |

> **Note:** In Odoo 19, `"storable"` products require the `stock` module. For maximum compatibility in reporting modules, prefer `"type": "consu"`.

---

## Transactional Steps

Transactional steps execute business operations against the database.
Products and partners are resolved by `code`/`ref` from previously created master data or from existing records.

---

### `create_purchase_order`

Creates and confirms a purchase order. Supports single-product and multi-line formats.

**Single-product format:**

```json
{
  "step": "create_purchase_order",
  "product": "product_avg",
  "qty": 5.0,
  "price": 100.0,
  "partner": "supplier_1",
  "currency": "RON"
}
```

**Multi-line format (using `products` list):**

```json
{
  "step": "create_purchase_order",
  "products": [
    {"product": "PROD-AVG-001", "qty": 5.0, "price": 100.0},
    {"product": "MP-001", "qty": 10.0, "price": 50.0}
  ],
  "partner": "supplier_1",
  "currency": "RON"
}
```

| Field | Required | Description |
|---|---|---|
| `product` | ✅ (single) | Product code to order |
| `qty` | ✅ (single) | Ordered quantity |
| `price` | ✅ (single) | Unit price |
| `products` | ✅ (multi) | List of `{product, qty, price}` objects |
| `partner` | ✅ | Partner `ref` or name |
| `currency` | — | ISO currency code (e.g. `"RON"`) |
| `notice` | — | If `true`, propagates `l10n_ro_notice = True` to the subsequent `receive_stock` step (Romanian NIR notice) |

The confirmed PO is stored as `last_purchase_order` in the execution context for use by subsequent steps.

---

### `receive_stock`

Receives goods on the last confirmed purchase order picking.
Supports both single-product and multi-product (`products` list) formats.
The picking is validated only after all moves are marked as received.

**Single product:**
```json
{
  "step": "receive_stock",
  "product": "product_avg",
  "qty": 5.0
}
```

**Multiple products:**
```json
{
  "step": "receive_stock",
  "products": [
    {"product": "product_avg", "qty": 5.0},
    {"product": "product_fifo", "qty": 3.0}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `product` | — | Product code to receive (single-product mode); if omitted, all products are received |
| `qty` | — | Quantity to receive (single-product mode); defaults to ordered quantity |
| `products` | — | List of `{product, qty}` objects for multi-product receive |
| `notice` | — | If `true`, sets `l10n_ro_notice = True` on the picking (Romanian NIR notice); overrides value from `create_purchase_order` |
| `checks` | — | Optional stock validation after this step (see **Checks** section) |

> **Note:** `notice: true` can also be set on `create_purchase_order` and will be propagated automatically to the subsequent `receive_stock` step.

---

### `return_stock`

Creates a stock return (reverse picking) for the last received stock picking.
Use this instead of `receive_stock` with a negative quantity.

```json
{
  "step": "return_stock",
  "qty": 3.0,
  "product": "product_avg"
}
```

| Field | Required | Description |
|---|---|---|
| `qty` | ✅ | Quantity to return (positive value) |
| `product` | — | Product code to return; if omitted, all products from the last receipt are returned |
| `checks` | — | Optional stock validation after this step (see **Checks** section) |

The return picking is created with reversed source/destination locations and `origin_returned_move_id` set correctly.

---

### `create_vendor_bill`

Creates and posts a vendor bill linked to the last purchase order.
Supports both single-product and multi-product (`products` list) formats for overriding invoice line quantities/prices.

**Single product:**
```json
{
  "step": "create_vendor_bill",
  "qty": 5.0,
  "price": 100.0
}
```

**Multiple products:**
```json
{
  "step": "create_vendor_bill",
  "products": [
    {"product": "product_avg", "qty": 5.0, "price": 100.0},
    {"product": "product_fifo", "qty": 3.0, "price": 80.0}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `qty` | — | Invoice quantity override for all lines (single-product mode) |
| `price` | — | Invoice unit price override for all lines (single-product mode) |
| `products` | — | List of `{product, qty, price}` objects to override specific lines by product |

---

### `create_sale_order`

Creates and confirms a sale order, delivers goods, and posts the customer invoice.
Supports both single-product and multi-product (`products` list) formats.

**Single product:**
```json
{
  "step": "create_sale_order",
  "product": "product_avg",
  "qty": 3.0,
  "price": 150.0,
  "partner": "customer_1",
  "currency": "RON"
}
```

**Multiple products:**
```json
{
  "step": "create_sale_order",
  "products": [
    {"product": "product_avg", "qty": 3.0, "price": 150.0},
    {"product": "product_fifo", "qty": 2.0, "price": 120.0}
  ],
  "partner": "customer_1",
  "currency": "RON"
}
```

| Field | Required | Description |
|---|---|---|
| `product` | ✅ (single) | Product code |
| `qty` | ✅ (single) | Quantity to sell |
| `price` | ✅ (single) | Unit sales price |
| `products` | ✅ (multi) | List of `{product, qty, price}` objects |
| `inv_qty` | — | Invoice quantity override (per line in `products`, or global in single mode) |
| `inv_price` | — | Invoice unit price override (per line in `products`, or global in single mode) |
| `partner` | ✅ | Partner `ref` or name |
| `currency` | — | ISO currency code |

---

### `create_invoice`

Creates a customer or vendor invoice manually (not linked to a PO/SO).

**Single product:**

```json
{
  "step": "create_invoice",
  "move_type": "out_invoice",
  "partner": "customer_1",
  "product": "product_avg",
  "qty": 2.0,
  "price": 150.0
}
```

**Multiple products:**

```json
{
  "step": "create_invoice",
  "move_type": "out_invoice",
  "partner": "customer_1",
  "products": [
    {"product": "product_avg", "qty": 2.0, "price": 150.0},
    {"product": "product_fifo", "qty": 1.0, "price": 200.0}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `move_type` | ✅ | `"out_invoice"` (customer), `"in_invoice"` (vendor), `"out_refund"`, `"in_refund"` |
| `partner` | ✅ | Partner `ref` or name |
| `product` | ✅ (single) | Product code |
| `qty` | ✅ (single) | Quantity |
| `price` | ✅ (single) | Unit price |
| `products` | ✅ (multi) | List of `{product, qty, price}` objects |
| `invoice_date` | — | Invoice date (ISO format, e.g. `"2026-04-01"`) |
| `date` | — | Alias for `invoice_date` (lower priority) |
| `ref` | — | Invoice reference / number (e.g. `"F.1/01.04.2026"`) |
| `key` | — | Explicit key to store the invoice in the execution context (auto-generated if omitted as `invoice_{move_type}_{safe_ref}`) |

The created invoice is stored in the execution context under the auto-generated key `invoice_{move_type}_{safe_ref}` (characters `/`, `.`, ` ` replaced with `_`) and also as `last_invoice`.

---

### `post_invoice`

Validates (posts) an invoice. Resolves the invoice in the following order:
1. By explicit `key` in the execution context.
2. By `ref` in the execution context (auto-generated key `invoice_{move_type}_{safe_ref}`).
3. By `ref` field in the database (draft invoices).
4. By `last_invoice` in the execution context.

```json
{
  "step": "post_invoice",
  "ref": "F.1/01.04.2026",
  "move_type": "out_invoice"
}
```

| Field | Required | Description |
|---|---|---|
| `key` | — | Explicit context key of the invoice to post |
| `ref` | — | Invoice reference to look up (combined with `move_type` to build the auto-key) |
| `move_type` | — | Invoice type used together with `ref` to build the auto-key (default: `"out_invoice"`) |
| `invoice_date` | — | If the invoice has no date, sets it before posting |

---

### `create_journal_entry`

Creates and posts a manual journal entry (nota contabilă) with explicit debit/credit lines.

```json
{
  "step": "create_journal_entry",
  "date": "2026-04-30",
  "ref": "Salarii aprilie 2026",
  "journal": "general",
  "lines": [
    {"account": "641", "debit": 10000.0, "credit": 0.0, "name": "Cheltuieli salarii"},
    {"account": "421", "debit": 0.0, "credit": 7500.0, "name": "Personal - salarii datorate"},
    {"account": "444", "debit": 0.0, "credit": 2500.0, "name": "Impozit pe salarii"}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `date` | — | Journal entry date (ISO format); defaults to today |
| `ref` | — | Reference / description of the journal entry |
| `journal` | — | Journal type: `"general"` (default), `"sale"`, `"purchase"`, `"cash"`, `"bank"` |
| `lines` | ✅ | List of journal lines with `account` (code), `debit`, `credit`, and optional `name` |

The posted journal entry is stored as `last_journal_entry` in the execution context.

---

### `create_payment`

Creates and posts a payment (cash or bank), with optional reconciliation against an existing invoice.

```json
{
  "step": "create_payment",
  "date": "2026-04-15",
  "amount": 600.0,
  "currency": "RON",
  "partner": "supplier_1",
  "payment_type": "outbound",
  "journal": "cash",
  "ref": "Plata partiala Elycontab",
  "invoice_ref": "F.5/04.04.2026",
  "invoice_move_type": "in_invoice"
}
```

| Field | Required | Description |
|---|---|---|
| `amount` | ✅ | Payment amount |
| `currency` | — | ISO currency code (e.g. `"RON"`, `"EUR"`); defaults to company currency |
| `partner` | ✅ | Partner `ref` or name |
| `payment_type` | — | `"outbound"` (pay supplier / default for `in_invoice`) or `"inbound"` (receive from customer) |
| `journal` | — | Journal type: `"cash"` or `"bank"` (default: `"cash"`) |
| `date` | — | Payment date (ISO format); defaults to today |
| `ref` | — | Payment reference / memo |
| `invoice_ref` | — | Reference of the invoice to reconcile with (optional) |
| `invoice_move_type` | — | Invoice type used together with `invoice_ref` to find the invoice (default: `"in_invoice"`) |

The posted payment is stored as `last_payment` in the execution context.

---

### `create_stock_picking`

Creates a stock picking (receipt or delivery).

```json
{
  "step": "create_stock_picking",
  "picking_type": "incoming",
  "product": "PROD-AVG-001",
  "qty": 5.0,
  "partner": "supplier_1"
}
```

| Field | Required | Description |
|---|---|---|
| `picking_type` | ✅ | `"incoming"` (receipt) or `"outgoing"` (delivery) |
| `product` | ✅ | Product code |
| `qty` | ✅ | Quantity |
| `partner` | — | Partner `ref` or name |

---

### `validate_picking`

Validates the last created stock picking.

```json
{
  "step": "validate_picking"
}
```

No additional fields required.

---

## Checks Section

Each transactional step can include a `checks` block to validate stock state after the step executes:

```json
{
  "step": "receive_stock",
  "checks": {
    "stock": {
      "product_avg": [
        {"qty": 5, "value": 500}
      ]
    }
  }
}
```

| Field | Description |
|---|---|
| `checks.stock` | Dict of `product_code → [{qty, value, location?}]` — validates on-hand quantity and stock value |

The `qty` and `value` in checks are validated as **deltas** relative to the initial stock snapshot taken at the start of the scenario. This means you specify the expected change, not the absolute value.

**Optional `location` filter:**

```json
"checks": {
  "stock": {
    "product_avg": [
      {"qty": 5, "value": 500, "location": "all"}
    ]
  }
}
```

| Location value | Description |
|---|---|
| `"all"` (default) | All internal locations |
| `"input"` | Input/receiving location |
| `"output"` | Output/shipping location |

---

## Expected Account Moves

The `expected_account_moves` section at the root of the scenario defines the accounting entries to validate after all steps complete:

```json
"expected_account_moves": [
  {
    "journal_type": "purchase",
    "line_ids": [
      {"account_code": "401", "debit": 0.0, "credit": 500.0},
      {"account_code": "371", "debit": 500.0, "credit": 0.0}
    ]
  }
]
```

| Field | Description |
|---|---|
| `journal_type` | Journal type to match: `"purchase"`, `"sale"`, `"general"`, `"stock"` |
| `line_ids` | List of expected journal lines |
| `line_ids[].account_code` | Account code prefix to match |
| `line_ids[].debit` | Expected debit amount (legacy format) |
| `line_ids[].credit` | Expected credit amount (legacy format) |
| `line_ids[].balance` | Expected net balance = debit − credit (preferred format) |

> **Delta validation:** All amounts are validated as **deltas** relative to the account balances at the start of the scenario (snapshot taken at `snapshot_stock` step). This ensures correct results even when the database already contains prior transactions.

**Using `balance` format (preferred):**

```json
"expected_account_moves": [
  {
    "journal_type": "stock",
    "line_ids": [
      {"account_code": "371000", "balance": 500.0},
      {"account_code": "408000", "balance": -500.0}
    ]
  }
]
```

A positive `balance` means net debit; a negative `balance` means net credit.

---

## Complete Example

```json
{
  "id": "ro_stock_avg_case_0001",
  "name": "[RO_STOCK_AVG] Case 1: Receptie totala, fara factura",
  "mode": "test",
  "lines": [
    {
      "step": "create_purchase_order",
      "product": "product_avg",
      "qty": 5.0,
      "price": 100.0,
      "partner": "supplier_1",
      "currency": "RON"
    },
    {
      "step": "receive_stock",
      "checks": {
        "stock": {
          "product_avg": [{"qty": 5, "value": 500}]
        }
      }
    }
  ],
  "expected_account_moves": [
    {
      "journal_type": "stock",
      "line_ids": [
        {"account_code": "371", "debit": 500.0, "credit": 0.0},
        {"account_code": "408", "debit": 0.0, "credit": 500.0}
      ]
    }
  ]
}
```

---

## Models

| Model | Description |
|---|---|
| `stock.test.scenario` | Stores the JSON scenario definition, mode, and state |
| `account.test.run` | Records each execution with log, result, and link to scenario |
| `stock.test.log` | Individual log lines for each step: step number, type, state (`ok`/`error`/`info`), message, and document reference |

---

## Dependencies

- `account` — accounting entries and journals
- `stock` — stock pickings and locations
- `stock_account` — stock valuation and accounting integration
- `purchase` — purchase orders and vendor bills

---

## Installation

```bash
./odoo/odoo-bin -c odoo.conf -d your_db -i deltatech_account_scenario --stop-after-init
```

---

## Running Tests

```bash
./odoo/odoo-bin -c odoo.conf -d o19_test -u deltatech_account_scenario \
  --test-tags=deltatech_account_scenario --stop-after-init
```

---

## License

LGPL-3 — © 2024 Terrabit / Dorin Hongu — [https://www.terrabit.ro](https://www.terrabit.ro)
