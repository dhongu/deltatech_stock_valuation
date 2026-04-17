
## Overview

`deltatech_stock_test` is an Odoo 19 module that provides a **JSON-driven framework** for testing stock management accounting scenarios. It allows developers and accountants to define business processes (stock receipts, invoices, deliveries, etc.) as JSON scenarios, execute them against a live Odoo database, and automatically validate the resulting accounting entries and stock valuations.

The module supports two modes of operation:
- **Test mode** — executes a scenario and validates that the generated account moves and stock values match the expected entries defined in the JSON.
- **Demo mode** — executes a scenario to generate demo/sample data without strict accounting validation.

---

## Features

### JSON-Driven Scenarios
- Define complete business processes as structured JSON, including steps (actions) and expected accounting/stock entries.
- Steps are divided into two categories:
  - **Master data steps** — create or resolve reference data (accounts, partners, product categories, products).
  - **Transactional steps** — execute business operations (purchase orders, stock receipts, vendor bills, sale orders, invoices, stock pickings).

### Accounting & Stock Validation
- After executing all steps, the runner compares the generated `account.move.line` entries against the `expected_account_moves` section of the JSON.
- Validates account codes, debit/credit amounts, and analytic accounts.
- Validates stock quantities and values per product via the `checks` section in each step.
- Reports mismatches clearly in the run log.

### UI Integration
- **Scenario form** — view, edit, and manage JSON scenarios directly in Odoo; import JSON files via the **Import JSON** button in the form header.
- **Run history** — each execution is recorded as a `stock.test.run` record with full execution log and validation result.
- **Buttons** — "Set Ready", "Execute Scenario", "Re-run Scenario", "View Runs" available from the scenario form.
- Menu: **Management Accounting Tests → Scenarios** and **Runs**.

### Built-in Scenario Library
- Ships with base data (`00_base_data.json`) defining shared product categories, partners, and products used across all scenarios.
- Includes demo scenarios for purchase/sale flows, inventory transfers, stock receipts with invoices, and stock pickings.
- Includes **140 Romanian stock accounting test scenarios** under `data/scenarios/ro_stock/`:
  - **70 FIFO scenarios** (`ro_stock_fifo_case_XXXX.json`) — covering FIFO cost method edge cases per Romanian accounting regulations.
  - **70 Average cost scenarios** (`ro_stock_avg_case_XXXX.json`) — covering weighted average cost method edge cases.

### Automated Tests
- Includes `TransactionCase` tests under `tests/test_stock_scenarios.py` covering:
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

Creates a customer or supplier partner.

```json
{
  "step": "create_partner",
  "name": "Furnizor Test SRL",
  "ref": "supplier_1",
  "supplier_rank": 1,
  "customer_rank": 0
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Partner name |
| `ref` | ✅ | Internal reference — used to resolve the partner in transactional steps (e.g. `"supplier_1"`) |
| `supplier_rank` | — | Set to `1` for suppliers |
| `customer_rank` | — | Set to `1` for customers |

---

### `create_product_category`

Creates a product category with cost method and valuation properties.

```json
{
  "step": "create_product_category",
  "name": "RO Stock AVG",
  "property_cost_method": "average",
  "property_valuation": "real_time"
}
```

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Category name |
| `property_cost_method` | — | `"standard"`, `"average"`, or `"fifo"` (default: `"standard"`) |
| `property_valuation` | — | `"real_time"` (perpetual/automatic) or `"periodic"` (manual) |

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
| `checks` | — | Optional stock validation after this step (see **Checks** section) |

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

---

### `post_invoice`

Validates (posts) the last created invoice.

```json
{
  "step": "post_invoice"
}
```

No additional fields required.

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
| `checks.stock` | Dict of `product_code → [{qty, value}]` — validates on-hand quantity and stock value |

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
| `line_ids[].debit` | Expected debit amount |
| `line_ids[].credit` | Expected credit amount |

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
| `stock.test.run` | Records each execution with log, result, and link to scenario |

---

## Dependencies

- `account` — accounting entries and journals
- `stock` — stock pickings and locations
- `stock_account` — stock valuation and accounting integration
- `purchase` — purchase orders and vendor bills

---

## Installation

```bash
./odoo/odoo-bin -c odoo.conf -d your_db -i deltatech_stock_test --stop-after-init
```

---

## Running Tests

```bash
./odoo/odoo-bin -c odoo.conf -d o19_test -u deltatech_stock_test \
  --test-tags=deltatech_stock_test --stop-after-init
```

---

## License

LGPL-3 — © 2024 Terrabit / Dorin Hongu — [https://www.terrabit.ro](https://www.terrabit.ro)
