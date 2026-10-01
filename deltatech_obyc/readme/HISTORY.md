## 19.0.1.0.6 (2026-10-01)

- New: valuation class on the product category. A product without its own valuation class
  uses the class of its category; the class set on the product still takes priority.

## 19.0.1.0.5 (2026-10-01)

- Fix: the "Transaction key could not be determined" error showed the literal placeholders
  `{source_usage}` / `{dest_usage}` instead of the location usages — `env._()` interpolates
  `%(name)s` placeholders, not `{name}`. The message now names the actual source and destination
  usages (e.g. `internal` to `consume`), in the English text and in the Romanian translation.

## 19.0.1.0.4 (2026-10-01)

- Fix (OBYC-001): the product line of a customer invoice, a vendor bill or a credit note
  got the valuation account of the rule, because the account was chosen from the line
  debit/credit, still 0 when the line is created. A vendor bill debited the stock account a
  second time (after the receipt entry) and left the GR/IR account (408) open; customer
  invoices booked the revenue on the stock account. The account is now chosen from the
  document type: customer invoice and credit note → destination account of the
  `stock_income` rule; vendor bill and credit note → source account of the
  `stock_receipt` rule; the valuation account only when that account is empty. Credit
  notes use the same account as the invoice.
- Docs: consultant sheet corrected after the accounting audit and the OBYC-001 fix: invoice
  accounts per document type, credit notes with storno, configuration for finished products,
  raw materials and production, vendor bill on 408, landed cost account, inventory differences
  (shortages, imputation, VAT, profit tax), price and exchange differences on 408, month-end
  procedure for deliveries not invoiced (OBYC-002) compatible with the D300 computed from tax
  tags; screenshots 01 and 10 regenerated, 11 (vendor bill) added. `DESCRIPTION.md`: account
  mapping examples follow the code convention. `readme/bugs.md`: OBYC-008 and OBYC-009 added.

## 19.0.1.0.3 (2026-10-01)

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
- Docs: consultant sheet updated to the current code (cost of goods sold at delivery, landed
  cost, storno returns, journal per valuation area), 10 screenshots regenerated in Romanian;
  the screenshot test checks the journal entries before taking the screenshots. Known bugs
  OBYC-005 (inventory adjustment keys swapped), OBYC-006 (OBYC entry without real-time
  valuation) and OBYC-007 (smaller defects) added to `readme/bugs.md`.

## 19.0.1.0.2 (2026-09-30)

- Own module icon in the flat style of the other modules.

## 19.0.1.0.1 (2026-08-19)

- Fix: dropship moves (supplier -> customer) for products with an OBYC valuation class were
  not valued — `stock.move.value` stayed 0, because the `stock_account` core fills this
  field only for `is_in` moves, not for `is_dropship` ones. The journal entry generated
  right after was posted with debit=0/credit=0 — apparently recorded, but with no value.
