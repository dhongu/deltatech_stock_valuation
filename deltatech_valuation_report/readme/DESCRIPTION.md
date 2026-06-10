## Product Valuation Check Report

Enterprise report (account.report framework) that verifies, per stock valuation account,
that the product valuation (`deltatech_stock_valuation`) is consistent with the accounting
balance — and explains any difference.

### Columns

- **Account Balance** — full balance of the account from posted journal items, up to the
  selected date
- **Valuation (lines with product)** — total of the journal items carrying a product,
  which is by definition what the product valuation aggregates
- **Difference (lines without product)** — journal items posted on stock accounts without
  a product; these cannot be allocated to any product valuation

### Usage

A caret action on each account row opens the journal items without product, so the
difference can be audited and fixed directly (assign the product or move the line to a
non-valuation account).

### Dependencies

- `account_reports` (Odoo Enterprise)
- `deltatech_stock_valuation`
