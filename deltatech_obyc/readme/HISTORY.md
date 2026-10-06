## 20.0.1.0.8 (2026-10-06)

- In the valuation class and account modifier dropdowns the code is shown in a second, dimmed
  column; both can also be searched by code. The plain name, `[CODE] Name`, is unchanged.

## 20.0.1.0.7 (2026-10-01)

- New: valuation class on the product category. A product without its own valuation class
  uses the class of its category; the class set on the product still takes priority.

## 20.0.1.0.6 (2026-10-01)

Port of the 19.0 documentation fixes after the accounting audit and the OBYC-001 fix,
adapted to Odoo 20.

- Docs: consultant sheet (`readme/FISA_CONSULTANT.md`): legal basis completed (OMFP items 53,
  69, 283 (2), 310; Fiscal Code art. 281, 282, 319 (16), 304, 25); invoice accounts per
  document type, credit notes with storno and the valuation area of the invoice line;
  configuration for finished products, raw materials and production; the same 408 on
  receipt, dropship and dropship return; vendor bill on 408 (new step 6b and screenshot 11);
  landed cost account = the account of the transport bill; inventory differences (shortages
  imputed without VAT, VAT adjustment Dr 635 / Cr 4426, profit tax); price and exchange
  differences left on 408; month-end procedure for deliveries not invoiced (OBYC-002): Dr 418
  / Cr 707 + 4428 and Dr 4428 / Cr 4427 in the month of the delivery, with the D300 tax tags
  on the 707 and 4427 lines (the D300 is computed from tax tags) and a reversal on day 1 of
  the next month; monthly reconciliation of the stock account per valuation area; the transit
  route between areas is no longer suggested (OBYC-009); error messages updated to the
  OBYC-007 fix; Odoo 20 menus.
- Docs: `readme/bugs.md`: OBYC-002 procedure and core wizard analysis, OBYC-008 (down payment
  wizard) and OBYC-009 (transit route at 0) checked in the Odoo 20 code; `DESCRIPTION.md`:
  the transit route is marked as not validated.
- Tests: the screenshot test seeds the income rule with 707 only in the destination account,
  uses the Romanian payable account (401) for the supplier, posts a vendor bill, checks the
  product line accounts of the customer invoice and of the vendor bill, and captures the vendor
  bill (`11_vendor_bill_408.png`).
- Code comment on credit notes corrected.

## 20.0.1.0.5 (2026-10-01)

Port of the 19.0 fixes (19.0.1.0.4 to 19.0.1.0.6).

- Fix (OBYC-001): the product line of a customer invoice, a vendor bill or a credit note
  got the valuation account of the rule, because the account was chosen from the line
  debit/credit, still 0 when the line is created. A vendor bill debited the stock account a
  second time (after the receipt entry) and left the GR/IR account (408) open; customer
  invoices booked the revenue on the stock account. The account is now chosen from the
  document type: customer invoice and credit note → destination account of the
  `stock_income` rule; vendor bill and credit note → source account of the
  `stock_receipt` rule; the valuation account only when that account is empty. Credit
  notes use the same account as the invoice.
- Fix (OBYC-005): the inventory adjustment keys were swapped — a gain used the
  `inventory_adjustment_minus` rule and a loss the `inventory_adjustment_plus` rule. A gain
  now uses `inventory_adjustment_plus` and a loss `inventory_adjustment_minus`. **Rules
  configured around the old behavior must swap their keys**; the update logs a warning for
  each rule that looks configured that way and does not change it.
- Fix (OBYC-006): stock entries were created for products with a valuation class even
  without real-time valuation, for consumables and for stock owned by a third party, and a
  missing rule blocked the validation of these moves. The core checks (storable product,
  real-time valuation, non-zero quantity, no third-party owner) now come before the rule
  lookup; a move the core does not value and whose locations have no transaction key gets no
  entry instead of an error.
- Fix (OBYC-007): the "Transaction key could not be determined" error showed the literal
  placeholders `{source_usage}` / `{dest_usage}` (`env._()` interpolates `%(name)s`); the "No
  account determination rule found" message shows the transaction key in the user's language;
  the rule title shows the key label and no "None" for an empty account modifier.
- Docs: `readme/bugs.md` aligned with 19.0 (OBYC-001/005/006/007 fixed, OBYC-002/003 analysis,
  OBYC-004 lowered to P3, OBYC-008/009 added), `DESCRIPTION.md` aligned with 19.0 (account
  mapping examples follow the code convention), consultant sheet.

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
