# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## OBYC-001 — P1: Invoice product lines get the valuation account instead of the income/expense account

- **Status:** Fixed in 19.0.1.0.4.
- **Location:** `models/account_move_line.py`, `_compute_account_id()`.
- **Actual behavior (before the fix):** The account was chosen from `line.debit` / `line.credit`, still 0 when the compute runs at line creation, so the line kept `acc_valuation_id`. A vendor bill debited the stock account a second time (after Dr 371 / Cr 408 of the receipt) and left 408 open; a vendor credit note lowered the stock a second time; a customer invoice booked the revenue on the stock account. The entries were balanced, so nothing failed.
- **Fix:** The account is chosen from the document type: sale documents (invoice, credit note, receipt) → `acc_dest_id` of the `stock_income` rule; purchase documents → `acc_src_id` of the `stock_receipt` rule; `acc_valuation_id` only when that account is empty. Credit notes use the same account as the invoice. With storno accounting (default for Romanian companies) a credit note is booked in red on the same side as the invoice (e.g. Dr 4111 −V / Cr 707 −V + Cr 4427 −V); without storno Odoo swaps the side.
- **Validation:** `tests/test_obyc_entries.py` posts a customer invoice, a customer credit note, a vendor bill after a receipt and a vendor credit note without recomputing the account, and checks the entries.
- **Data already posted:** Invoices posted before 19.0.1.0.4 keep the wrong account; check the balances of the stock accounts against the valuation report and of 408 against the receipts not yet invoiced, and correct them by journal entry.

## OBYC-002 — P2: No accrued revenue (418) for goods delivered but not invoiced at month end

- **Status:** Open (known limitation).
- **Location:** No implementation; the cost is booked at delivery by `models/stock_move.py`.
- **Trigger:** Deliver goods in month M and post the customer invoice in month M+1.
- **Actual behavior:** The cost of goods sold (607/711) is booked in month M, the revenue (707/701) only in month M+1.
- **Expected behavior / manual procedure until a fix:** VAT is due at delivery (Fiscal Code art. 282 (1)); art. 319 (16) only requires the invoice to be issued by the 15th of the next month and does not move the chargeability. The Romanian D300 of `l10n_ro` is computed from the tax tags of the invoice lines (`account_tax_report_data.xml`, engine `tax_tags`), not from the balance of 4427, so a manual entry crediting 4427 does not reach the D300. Use **one** of the two options, never both (otherwise the revenue is booked twice in month M):
  - (a) preferred: the customer invoice with its accounting date in month M (issued in month M, or by the 15th of month M+1 if the period is not locked). Revenue and VAT reach month M through the invoice, with no 418 entry and no reversal.
  - (b) the invoice with its accounting date in month M+1: at the end of month M, a manual journal entry Dr 418 = Cr 707 (701 for finished products), **without VAT**, based on the delivery notes, reversed on day 1 of month M+1 (Reverse Entry with a future date: the reversal is posted at that date). The invoice of month M+1 is posted normally (Dr 4111 / Cr 707 + 4427); without the reversal the revenue would be booked twice. The VAT of the delivery is added manually to the D300 of month M and removed from the D300 of month M+1, where the invoice brings it.
  - VAT on cash basis (art. 282 (3)): the VAT stays on 4428 until collection, as for any invoice.
  - The core accrued revenue wizard (`account/wizard/accrued_orders.py`) cannot be used for products with a valuation class: it calls `get_product_accounts()` without a transaction key and `product.template._get_product_accounts()` raises "Transaction key is not defined".
- **Impact:** Revenue and expenses of the same transaction fall in different months (OMFP 1802/2014, item 53 (2)–(3) and item 310 (3)).
- **Evidence:** Confirmed with the accounting reference (Pacioli) on 2026-10-01. An earlier version of this entry proposed Dr 418 / Cr 707 + 4427 (or 4428) and clearing by Dr 4111 / Cr 418: the VAT of such an entry does not reach the D300, and Odoo posts the invoice of month M+1 on 707 (Dr 4111 / Cr 707 + 4427), so without a reversal the revenue is booked twice.
- **Core wizard (verified in the code on 2026-10-01):** `account/wizard/accrued_orders.py`, `_get_computed_account()` (l.102-107), calls `get_product_accounts()` without a transaction key, so the "Accrued Revenue Entry" action of a sale order stops with "Transaction key is not defined" on OBYC products. Passing `transaction_key=stock_income` in the context is not enough: `product.template._get_product_accounts()` maps `income` to the source account of the rule, while invoices use its destination account (OBYC-001).
- **Suggested fix:** Start from the core wizard, which already builds the entry from the delivered and not invoiced quantities and posts the reversal at the date chosen: override `_get_computed_account()` for products with a valuation class to return the same account as the invoice line (`stock_income` → destination account, `stock_receipt` → source account), from a helper shared with `account.move.line._compute_account_id()`. The wizard then books Dr 418 / Cr 707 (701), without VAT, reversed on day 1 of month M+1 — option (b) above. Decision pending.
- **Validation needed:** A test with a delivery in month M and the invoice in month M+1, checking the accrual entry, its reversal, the revenue booked only once and the D300 VAT.

## OBYC-003 — P2: Consignment, goods sent for testing and goods kept at the customer's disposal are expensed at shipment

- **Status:** Open (known limitation).
- **Location:** `models/stock_move.py`, `_compute_transaction_key()`: every internal → customer move uses `stock_delivery`.
- **Trigger:** Ship goods on consignment, for testing, or as goods held for the customer, through a customer location.
- **Actual behavior:** The shipment books the cost of goods sold right away (e.g. Dr 607 / Cr 371).
- **Expected behavior:** The cost is booked when control is transferred: consignment → Dr 357 / Cr 371 (or Dr 354 / Cr 345) at shipment and Dr 607 / Cr 357 when the consignee sells; testing → at acceptance; goods at the customer's disposal → when the customer takes them out of the warehouse.
- **Impact:** Expenses booked too early; goods still owned by the company leave the stock accounts.
- **Evidence:** OMFP 1802/2014, items 283, 443–445; Fiscal Code art. 281 (2). Confirmed with the accounting reference (Pacioli) on 2026-10-01.
- **Already possible (verified 2026-10-01):** the account modifier of the picking type (`stock.picking.type.account_modifier_id`, used by `stock.move._get_rule_account()`) gives a dedicated `stock_delivery` rule to a "Consignment shipment" operation type: Cr 371 / Dr 357 (valuation account 371, destination account 357) at shipment, the first stage. What is missing is the second stage (Dr 607 / Cr 357 when the consignee sells or the customer accepts the goods), which has no stock move.
- **Suggested fix:** Keep the goods in an internal "consignment" location of the company (they are still its property) and book the two stages through stock moves: stock → consignment location with an operation type with modifier (Dr 357 / Cr 371), consignment location → customer with a second operation type with modifier (`stock_delivery` rule: Dr 607 / Cr 357). The second stage works today; the first needs the value of internal moves, which Odoo 19 does not set (same cause as OBYC-009). Decision pending.
- **Validation needed:** Tests for each flow, checking the entries at shipment and at the transfer of control.

## OBYC-004 — P3: A full invoice issued before delivery is booked as revenue, not as an advance

- **Status:** Open (accounting policy limitation, not a defect of the module). Priority lowered from P2 on 2026-10-01: the core books the same way for any product, and the standard solution is the down payment invoice (Dr 4111 / Cr 419 + 4427), which the final invoice clears; its OBYC blocker is tracked separately as OBYC-008.
- **Location:** No implementation; the revenue line uses the `stock_income` rule regardless of the delivery.
- **Trigger:** Post a full customer invoice (not a down payment) before the goods are delivered and before control is transferred.
- **Actual behavior:** The invoice credits 707/701.
- **Expected behavior:** Without transfer of control, the amount is an advance: Dr 4111 / Cr 419 + 4427 (VAT due when the invoice is issued, Fiscal Code art. 282 (2) a)). At delivery the cost is booked (Dr 607 / Cr 371). With down-payment invoices, the final invoice that deducts the advance clears 419 and its VAT, with no manual entry. Only when a full invoice posted before delivery was reclassified manually to 419 is the revenue recognized at delivery by Dr 419 = Cr 707 (701), without new VAT; OMFP item 311^1 speaks of amounts collected, for invoices not yet collected this is the usual practice, to be confirmed with the accountant.
- **Probable blocker (not tested):** the core down-payment wizard (`sale/wizard/sale_make_invoice_advance.py`, `_get_down_payment_account`) calls `get_product_accounts()` without a transaction key, so on orders with OBYC products it should stop with "Transaction key is not defined" (same mechanism as the accrued revenue wizard, OBYC-002). To confirm with a test.
- **Impact:** Revenue recognized before the transfer of control (OMFP 1802/2014, items 311^1 (2), 441, 442). Not invoicing the cost lines (OBYC behavior) does not solve this case on its own. "Bill and hold" (ex-works) is an exception: goods leave the stock when ownership is transferred.
- **Evidence:** Confirmed with the accounting reference (Pacioli) on 2026-10-01.
- **Suggested fix:** Detect invoices posted before the related delivery and route their revenue to 419 (or require down-payment invoices), then regularize at delivery.
- **Validation needed:** Tests with an invoice before delivery, checking the 419 entry and its regularization; a bill-and-hold case.

## OBYC-005 — P2: Inventory adjustment keys are swapped

- **Status:** Fixed in 19.0.1.0.6.
- **Location:** `models/stock_move.py`, `_compute_transaction_key()`.
- **Actual behavior (before the fix):** A loss (internal → inventory location) used `inventory_adjustment_plus`; a gain (inventory location → internal) used `inventory_adjustment_minus`, contrary to the key names and `readme/DESCRIPTION.md`. A rule configured by its name booked gains as losses and losses as gains; the entry was balanced, so nothing failed.
- **Fix:** A gain uses `inventory_adjustment_plus`, a loss `inventory_adjustment_minus`.
- **Validation:** `tests/test_obyc_entries.py`, `test_11_inventory_gain` (Dr stock / Cr gain account) and `test_12_inventory_loss` (Dr loss account / Cr stock), through a real inventory adjustment.
- **Migration:** Rules are not changed automatically. On update, `migrations/19.0.1.0.6/post-migration.py` logs a warning ("OBYC-005: account determination rule …") for each rule that looks configured for the old behavior (an `inventory_adjustment_plus` rule with only a destination account, an `inventory_adjustment_minus` rule with a source account). Check these rules and swap their keys; otherwise gains are booked as losses and losses as gains from the update on. Entries posted before the update are not changed.

## OBYC-006 — P2: OBYC journal entries are created for products without real-time valuation

- **Status:** Fixed in 19.0.1.0.6. Priority raised from P3 on 2026-10-01: a missing rule or an unmapped location pair blocked the validation of any move of a product with a valuation class.
- **Location:** `models/stock_move.py`, `_should_create_account_move()`.
- **Actual behavior (before the fix):** The override only checked the rule accounts and skipped the core checks (`is_storable`, `valuation == "real_time"`, non-zero quantity, third-party owner), so a journal entry was created for periodic valuation, consumables and stock owned by a third party (at 0). Worse, it looked the rule up first: without a rule (`RedirectWarning`) or for a location pair without a transaction key (`UserError`), the validation stopped.
- **Fix:** The core checks come first: storable product, real-time valuation of the move company, non-zero quantity, not owned by a third party (`_should_exclude_for_valuation()` on the move or on all its lines). A move that the core does not value (neither in, out nor dropship) and whose location pair has no transaction key gets no entry instead of an error. Then the OBYC rule is checked as before. `is_valued` is not required: drop shipments and transfers between valuation areas are not in/out moves in the core but have their own OBYC keys.
- **Still blocking, on purpose:** a real-time valued move without a rule (`RedirectWarning` with a link to the configuration), and a valued move whose location pair has no transaction key (`UserError`), because the stock value would change without an entry.
- **Validation:** `tests/test_obyc_entries.py`, `test_13_periodic_valuation_no_entry`, `test_14_consumable_without_rules`, `test_15_owner_stock_no_entry`, `test_16_unmapped_locations_not_valued`.

## OBYC-007 — P3: Smaller defects found while updating the consultant sheet

- **Status:** Fixed (the defects): the error message in 19.0.1.0.5 (PR #43), the rest in 19.0.1.0.6; two items are not defects (see below).
- **Error message without the location types (fixed):** `_compute_transaction_key()` used `{source_usage}` / `{dest_usage}`, but `env._()` formats with `%`, so the message showed the braces literally. It now uses `%(source_usage)s` / `%(dest_usage)s`, in the code and in `i18n/ro.po`. Fixed in 19.0.1.0.5 by PR #43 (danila12). Test: `test_stock_move_account_determination.py`, `test_05_unknown_transaction_key_message`.
- **Transaction key label in English (fixed):** the `RedirectWarning` of `_get_rule_account()` read the raw selection; it now uses `_description_selection()`, so the label follows the user's language. Test: `test_obyc_account_determination.py`, `test_10_missing_rule_message_translated`.
- **Rule title (fixed):** `_compute_display_name()` showed the technical key and "None" for an empty modifier; it now shows the key label and leaves out empty parts (e.g. `Stock Delivery - Test Class - Test Area`). Test: `test_05_display_name_computation` (it asserted the old title).
- **Wrong examples in DESCRIPTION.md (fixed on 2026-10-01, documentation only):** the "Typical Account Mappings" table (e.g. `stock_delivery` with source 371, destination 607, valuation 378) would generate Dr 378 / Cr 371. The table and the descriptions of the keys and accounts follow the convention of the code.
- **Not a defect — storno on products without a valuation class:** the storno inversion in `_get_account_move_line_vals()` also applies to the core lines of returns of products without a valuation class. With `account_storno` enabled the company books every return in red, whatever the product; this is the intended behavior.
- **Not a defect — landed cost on goods partly delivered:** the core `stock_landed_costs` capitalizes only the part still in stock; the account of the cost line for the delivered part is checked with the accountant. Core behavior, documented in the consultant sheet.

## OBYC-008 — P2: The down payment wizard probably fails on orders with OBYC products

- **Status:** Open (deduced from the code, not verified by a test).
- **Location:** `sale/wizard/sale_make_invoice_advance.py`, `_get_down_payment_account()`, which calls `get_product_accounts()` without a transaction key; `models/product_template.py`, `_get_product_accounts()`.
- **Trigger:** Create a down payment invoice from a sale order with products that have an OBYC valuation class.
- **Expected failure:** "Transaction key is not defined", raised by `_get_product_accounts()` when the context has no `transaction_key`.
- **Impact:** Down payment invoices (OBYC-004, Dr 4111 / Cr 419) cannot be created from the wizard for these orders.
- **Suggested fix:** Run the wizard with a transaction key (or `skip` and the down payment account from the settings), as for the COGS lines.
- **Validation needed:** A test that creates a down payment invoice from an order with an OBYC product.

## OBYC-009 — P2: Transfers through the transit location may be posted at 0

- **Status:** Open (deduced from the code, not verified by a test).
- **Location:** `models/stock_move.py`, `_get_account_move_line_vals()` (uses `self.value` and `_get_valued_qty()`).
- **Trigger:** An internal transfer between two valuation areas through the transit location, with rules for `internal_transfer_out` / `internal_transfer_in`.
- **Expected failure:** In Odoo 19 a stock → transit move is neither `is_in` nor `is_out`, so `_set_value()` does not fill `stock.move.value`; the OBYC entry would be posted with value and quantity 0.
- **Impact:** The value does not move between the areas although the entry looks posted.
- **Validation needed:** A test of the transit route with both rules defined, checking the value of both entries.

## OBYC-010 — All internal users can modify account determination rules across companies

- **Priority:** P1
- **Status:** Open (2026-10-02).
- **Source:** `security/ir.model.access.csv; models/product_account_determination.py`.
- **Trigger:** A non-accounting internal user invokes create/write/unlink on product.account.determination through RPC.
- **Observed behavior:** The ACL gives base.group_user all four permissions and there are no company rules for this new model in the declared suite. Users can alter or delete rules for another company, affecting the accounts selected on subsequent invoices and stock entries. Menu visibility does not restrict these model operations.
- **Evidence:** Reviewed the ACL, new model, rule lookup and manifest security loading. No database/RPC reproduction; findings assume no external extension adds stricter global rules.
- **Suggested fix / regression check:** Limit configuration writes to an appropriate accounting administration group and enforce company isolation with record rules. Cover direct ORM/RPC mutations by a normal internal user.
