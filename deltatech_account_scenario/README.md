# deltatech_account_scenario

**Stock Test — Management Accounting Test Framework**

An advanced Odoo 19 module for testing stock and management accounting functionality via JSON-driven scenarios. Inspired
by and compatible with the test patterns used in `l10n_ro_stock_account`.

---

## Overview

This module allows you to define test scenarios as JSON documents stored in the database. Each scenario describes a
sequence of business operations (purchases, sales, inventory adjustments, internal transfers) along with inline
assertions that verify stock quantities and accounting balances after each step.

Scenarios can be used for:

- **Automated regression tests** — validate that accounting entries are correct after module upgrades or configuration
  changes.
- **Demo data generation** — populate a database with realistic stock and accounting data for demonstrations or
  onboarding.
- **Manual QA** — run scenarios from the UI with a single button click and inspect the execution log.

---

## Features

### Advanced Step Types (inspired by `l10n_ro_stock_account`)

| Step type          | Description                                                         |
| ------------------ | ------------------------------------------------------------------- |
| `purchase`         | Create PO, confirm, receive goods, create and post vendor bill      |
| `sale`             | Create SO, confirm, deliver goods, create and post customer invoice |
| `inventory`        | Set stock quantity via inventory adjustment (`stock.quant`)         |
| `transfer_direct`  | Direct internal transfer between two locations (one picking)        |
| `transfer_transit` | Two-step internal transfer via transit location (push rules)        |
| `consume`          | Outgoing picking for consumption (e.g. manufacturing input)         |
| `usage_giving`     | Outgoing picking for usage giving operations                        |

### Setup Step Types

| Step type                 | Description                                      |
| ------------------------- | ------------------------------------------------ |
| `create_product_category` | Create or reuse a product category               |
| `create_partner`          | Create or reuse a partner (vendor/customer)      |
| `create_product`          | Create or reuse a product with optional accounts |
| `create_account`          | Create or reuse an account.account               |

### Legacy Step Types (backward compatible)

| Step type              | Description                                   |
| ---------------------- | --------------------------------------------- |
| `create_invoice`       | Create an account.move (in/out invoice)       |
| `post_invoice`         | Post an invoice by key                        |
| `create_stock_picking` | Create a stock picking by picking_type_code   |
| `validate_picking`     | Confirm, assign and validate a picking by key |

### Inline Checks

After any step, add a `"checks"` key to verify state immediately:

```json
{
  "step": "purchase",
  "product_code": "PROD-001",
  "qty": 10,
  "price": 100,
  "checks": {
    "stock": {
      "PROD-001": [{"qty": 10, "value": 1000}]
    },
    "account": {
      "371000": 1000
    }
  }
}
```

- **`checks.stock`** — verifies `stock.quant` quantity and value per product/location.
- **`checks.account`** — verifies cumulative balance of posted `account.move.line` per account code (same logic as
  `l10n_ro_stock_account`).

---

## JSON Scenario Format

```json
{
  "name": "Scenario Name",
  "lines": [
    {
      "step": "<step_type>",
      ... step-specific fields ...,
      "checks": {
        "stock": { "<product_code>": [{"location": "WH/Stock", "qty": 10, "value": 1000}] },
        "account": { "<account_code>": <expected_balance> }
      }
    }
  ],
  "expected_account_moves": [
    {
      "journal": "Journal Name",
      "line_ids": [
        {"account": "4111", "debit": 0, "credit": 1650},
        {"account": "707",  "debit": 1500, "credit": 0}
      ]
    }
  ]
}
```

### Step field reference

#### `purchase`

```json
{
  "step": "purchase",
  "partner_name": "Vendor Name",
  "product_code": "PROD-001",
  "qty": 10.0,
  "price": 100.0,
  "inv_qty": 10.0,
  "inv_price": 100.0
}
```

#### `sale`

```json
{
  "step": "sale",
  "partner_name": "Customer Name",
  "product_code": "PROD-001",
  "qty": 5.0,
  "price": 150.0,
  "inv_qty": 5.0,
  "inv_price": 150.0
}
```

#### `inventory`

```json
{
  "step": "inventory",
  "product_code": "PROD-001",
  "qty": 100.0,
  "location": "WH/Stock"
}
```

#### `transfer_direct`

```json
{
  "step": "transfer_direct",
  "product_code": "PROD-001",
  "qty": 30.0,
  "location": "WH/Stock",
  "location1": "WH/Output"
}
```

#### `transfer_transit`

```json
{
  "step": "transfer_transit",
  "product_code": "PROD-001",
  "qty": 20.0,
  "location": "WH/Stock"
}
```

#### `create_product_category`

```json
{
  "step": "create_product_category",
  "name": "Marfuri",
  "property_cost_method": "average",
  "property_valuation": "real_time"
}
```

`property_cost_method`: `standard`, `average`, `fifo` `property_valuation`: `manual_periodic`, `real_time`

#### `create_product`

```json
{
  "step": "create_product",
  "code": "PROD-001",
  "name": "Product Name",
  "categ_key": "categ_Marfuri",
  "standard_price": 100.0,
  "list_price": 150.0,
  "type": "consu"
}
```

---

## Models

| Model                 | Description                                     |
| --------------------- | ----------------------------------------------- |
| `stock.test.scenario` | Stores the JSON scenario definition             |
| `stock.test.run`      | Execution record with log, state, error message |

### `stock.test.scenario` fields

| Field         | Type      | Description                                    |
| ------------- | --------- | ---------------------------------------------- |
| `name`        | Char      | Scenario name                                  |
| `description` | Text      | Human-readable description                     |
| `json_data`   | Text      | Raw JSON scenario definition                   |
| `mode`        | Selection | `demo` (data only) or `test` (with validation) |
| `state`       | Selection | `draft` → `ready` → `executed`                 |

### `stock.test.run` fields

| Field               | Type      | Description                   |
| ------------------- | --------- | ----------------------------- |
| `scenario_id`       | Many2one  | Link to scenario              |
| `state`             | Selection | `running`, `passed`, `failed` |
| `log`               | Text      | Step-by-step execution log    |
| `validation_result` | Text      | Accounting validation results |
| `error_message`     | Text      | Error details if failed       |

---

## Dependencies

- `account` — accounting entries validation
- `stock` — stock operations
- `stock_account` — stock valuation and accounting
- `purchase` — purchase orders (for `purchase` step)
- `sale_management` — sale orders (for `sale` step)

---

## Installation

```bash
./odoo/odoo-bin -c odoo18.conf -d mydb -i deltatech_account_scenario --stop-after-init
```

---

## Running Tests

```bash
./odoo/odoo-bin -c odoo18.conf -d o19_test \
  -u deltatech_account_scenario \
  --test-tags=deltatech_account_scenario \
  --stop-after-init
```

---

## Comparison with `l10n_ro_stock_account`

| Feature                    | `l10n_ro_stock_account`  | `deltatech_account_scenario`        |
| -------------------------- | ------------------------ | ----------------------------- |
| Step execution engine      | Python `TransactionCase` | Odoo model (`stock.test.run`) |
| Scenario storage           | Hardcoded in test files  | JSON in database              |
| UI execution               | No                       | Yes (button in form view)     |
| Inline checks per step     | Yes                      | Yes (same format)             |
| Account balance checks     | Yes                      | Yes (same logic)              |
| Stock qty/value checks     | Yes                      | Yes (same logic)              |
| `purchase` / `sale` steps  | Yes                      | Yes                           |
| `transfer_direct/transit`  | Yes                      | Yes                           |
| `inventory` adjustment     | Yes                      | Yes                           |
| `consume` / `usage_giving` | Yes                      | Yes                           |
| Demo data generation mode  | No                       | Yes (`mode=demo`)             |
| Reusable across modules    | No (per-module tests)    | Yes (shared framework)        |

---

## License

LGPL-3.0 or later — see [LICENSE](LICENSE) file.

## Author

Deltatech — <https://www.terrabit.ro>
