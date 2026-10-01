## 20.0.1.0.5 (2026-10-01)

- Fix (OBYC-001): the product line of a customer invoice, a vendor bill or a credit note
  got the valuation account of the rule, because the account was chosen from the line
  debit/credit, still 0 when the line is created. A vendor bill debited the stock account a
  second time (after the receipt entry) and left the GR/IR account (408) open; customer
  invoices booked the revenue on the stock account. The account is now chosen from the
  document type: customer invoice and credit note → destination account of the
  `stock_income` rule; vendor bill and credit note → source account of the
  `stock_receipt` rule; the valuation account only when that account is empty. Credit
  notes use the same account as the invoice.

## 20.0.1.0.4 (2026-10-01)

- Docs: consultant sheet (`readme/FISA_CONSULTANT.md`) brought to Odoo 20, with the
  11-section structure from 19.0: cost of goods sold at delivery, sale invoice without COGS
  lines, landed cost, return without the selection wizard, negative move value on outgoing
  moves and the *Keep move value on retroactive recompute* setting.
- Docs: screenshots regenerated from `tests/test_screenshots.py` (delivery entry, sale invoice
  and landed cost entry added); the test checks the Dr/Cr of the entries before capturing.
- Docs: known limitations OBYC-005 to OBYC-007 added to `readme/bugs.md`.

## 20.0.1.0.3 (2026-10-01)

- Fix: validating a landed cost on a product with an OBYC valuation class crashed with
  `AttributeError: 'int' object has no attribute 'id'`. `_get_product_accounts` returned
  account ids instead of `account.account` records, which the core (fiscal position
  `map_account`, landed cost entries) expects.
- Fix: a customer invoice for a product with an OBYC valuation class in real-time valuation
  could not be posted ("Transaction key is not defined"). The core builds the COGS lines
  of the invoice without a transaction key. With OBYC the cost of goods sold is already
  booked at delivery (`stock_delivery` key), so the invoice now gets no COGS lines for
  these products; other products keep the standard behavior.
- Fix: an invoice with two or more products with an OBYC valuation class failed with
  "Expected singleton". `account.move.line._compute_account_id` read the product,
  account modifier and company from all the lines (`self`) instead of the current line.
- Docs: the description states that, with OBYC, the cost of goods sold is booked at
  delivery, not at invoicing; known limitations are listed in `readme/bugs.md`.

## 20.0.1.0.2 (2026-10-01)

- Migration to Odoo 20: in 20 `stock.move.value` is negative on outgoing moves; the OBYC
  journal entry keeps posting the absolute value, so the Dr/Cr amounts are the same as in 19.
- Odoo 20 replays the valuation and rewrites the value of outgoing moves already done when an
  incoming move is backdated, a done quantity is edited or a vendor bill revalues a receipt.
  For products with an OBYC valuation class the move value stays the one posted at validation
  (as in 19), consistent with the OBYC journal entry; other products keep the Odoo 20 behaviour.
  This applies only while the company setting *Keep move value on retroactive recompute*
  (`deltatech_valuation_area`) is enabled (the default); when disabled, OBYC products also
  follow the standard Odoo 20 recompute.

## 19.0.1.0.2 (2026-09-30)

- Own module icon in the flat style of the other modules.

## 19.0.1.0.1 (2026-08-19)

- Fix: dropship moves (supplier -> customer) for products with an OBYC valuation class were
  not valued — `stock.move.value` stayed 0, because the `stock_account` core fills this
  field only for `is_in` moves, not for `is_dropship` ones. The journal entry generated
  right after was posted with debit=0/credit=0 — apparently recorded, but with no value.
