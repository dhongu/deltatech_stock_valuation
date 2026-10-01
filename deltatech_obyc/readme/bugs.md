# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## OBYC-001 — P1: Invoice product lines get the valuation account instead of the income/expense account

- **Status:** Fixed in 19.0.1.0.4.
- **Location:** `models/account_move_line.py`, `_compute_account_id()`.
- **Actual behavior (before the fix):** The account was chosen from `line.debit` / `line.credit`, still 0 when the compute runs at line creation, so the line kept `acc_valuation_id`. A vendor bill debited the stock account a second time (after Dr 371 / Cr 408 of the receipt) and left 408 open; a vendor credit note lowered the stock a second time; a customer invoice booked the revenue on the stock account. The entries were balanced, so nothing failed.
- **Fix:** The account is chosen from the document type: sale documents (invoice, credit note, receipt) → `acc_dest_id` of the `stock_income` rule; purchase documents → `acc_src_id` of the `stock_receipt` rule; `acc_valuation_id` only when that account is empty. Credit notes use the same account as the invoice; Odoo only swaps the side.
- **Validation:** `tests/test_obyc_entries.py` posts a customer invoice, a customer credit note, a vendor bill after a receipt and a vendor credit note without recomputing the account, and checks the entries.
- **Data already posted:** Invoices posted before 19.0.1.0.4 keep the wrong account; check the balances of the stock accounts against the valuation report and of 408 against the receipts not yet invoiced, and correct them by journal entry.

## OBYC-002 — P2: No accrued revenue (418) for goods delivered but not invoiced at month end

- **Status:** Open (known limitation).
- **Location:** No implementation; the cost is booked at delivery by `models/stock_move.py`.
- **Trigger:** Deliver goods in month M and post the customer invoice in month M+1.
- **Actual behavior:** The cost of goods sold (607/711) is booked in month M, the revenue (707/701) only in month M+1.
- **Expected behavior:** At the end of month M, the revenue for delivered and not invoiced goods is booked on 418 (Dr 418 / Cr 707 or 701 + 4428), and cleared when the invoice is posted (Dr 4111 / Cr 418).
- **Impact:** Revenue and expenses of the same transaction fall in different months (OMFP 1802/2014, item 53 (3) and item 310 (3)). VAT is due at delivery (Fiscal Code art. 281 (1), 282 (1)), so the delivery must appear in the D300 of month M.
- **Evidence:** Confirmed with the accounting reference (Pacioli) on 2026-10-01.
- **Suggested fix:** A month-end accrual entry for delivered and not invoiced lines, reversed or offset when the invoice is posted. The VAT treatment (4428 transferred to 4427 in month M, or 4427 directly) depends on the client's accounting policy and must be checked.
- **Validation needed:** A test with a delivery in month M and the invoice in month M+1, checking the accrual entry, its clearing and the D300 VAT.

## OBYC-003 — P2: Consignment, goods sent for testing and goods kept at the customer's disposal are expensed at shipment

- **Status:** Open (known limitation).
- **Location:** `models/stock_move.py`, `_compute_transaction_key()`: every internal → customer move uses `stock_delivery`.
- **Trigger:** Ship goods on consignment, for testing, or as goods held for the customer, through a customer location.
- **Actual behavior:** The shipment books the cost of goods sold right away (e.g. Dr 607 / Cr 371).
- **Expected behavior:** The cost is booked when control is transferred: consignment → Dr 357 / Cr 371 (or Dr 354 / Cr 345) at shipment and Dr 607 / Cr 357 when the consignee sells; testing → at acceptance; goods at the customer's disposal → when the customer takes them out of the warehouse.
- **Impact:** Expenses booked too early; goods still owned by the company leave the stock accounts.
- **Evidence:** OMFP 1802/2014, items 283, 443–445; Fiscal Code art. 281 (2). Confirmed with the accounting reference (Pacioli) on 2026-10-01.
- **Suggested fix:** Separate transaction keys (or an account modifier on the picking type) for consignment, testing and goods held for the customer, with a second move for the moment control is transferred.
- **Validation needed:** Tests for each flow, checking the entries at shipment and at the transfer of control.

## OBYC-004 — P2: A full invoice issued before delivery is booked as revenue, not as an advance

- **Status:** Open (known limitation).
- **Location:** No implementation; the revenue line uses the `stock_income` rule regardless of the delivery.
- **Trigger:** Post a full customer invoice (not a down payment) before the goods are delivered and before control is transferred.
- **Actual behavior:** The invoice credits 707/701.
- **Expected behavior:** Without transfer of control, the amount is an advance: Dr 4111 / Cr 419 + 4427. At delivery the cost is booked (Dr 607 / Cr 371) and the advance is regularized (Dr 419 / Cr 4111, with the VAT reversal), against the final revenue.
- **Impact:** Revenue recognized before the transfer of control (OMFP 1802/2014, items 311^1 (2), 441, 442). Not invoicing the cost lines (OBYC behavior) does not solve this case on its own. "Bill and hold" (ex-works) is an exception: goods leave the stock when ownership is transferred.
- **Evidence:** Confirmed with the accounting reference (Pacioli) on 2026-10-01.
- **Suggested fix:** Detect invoices posted before the related delivery and route their revenue to 419 (or require down-payment invoices), then regularize at delivery.
- **Validation needed:** Tests with an invoice before delivery, checking the 419 entry and its regularization; a bill-and-hold case.

## OBYC-005 — P2: Inventory adjustment keys are swapped

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_compute_transaction_key()`.
- **Trigger:** Validate an inventory adjustment for a product with an OBYC valuation class.
- **Actual behavior:** A loss (internal → inventory location) uses `inventory_adjustment_plus`; a gain (inventory location → internal) uses `inventory_adjustment_minus`.
- **Expected behavior:** A gain uses `inventory_adjustment_plus` and a loss uses `inventory_adjustment_minus`, as the key names and `readme/DESCRIPTION.md` say.
- **Impact:** A rule configured by its name books gains as losses and losses as gains. The entry is balanced, so nothing fails.
- **Evidence:** `case "internal", "inventory": tr_key = "inventory_adjustment_plus"` and `case "inventory", "internal": tr_key = "inventory_adjustment_minus"`.
- **Suggested fix:** Swap the two keys, with a migration note for the databases whose rules were configured around the current behavior.
- **Validation needed:** A test with a positive and a negative adjustment, checking the rule and the accounts used.

## OBYC-006 — P3: OBYC journal entries are created for products without real-time valuation

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_should_create_account_move()`.
- **Trigger:** A product with an OBYC valuation class in a category with manual (periodic) valuation, or a non-valued move.
- **Actual behavior:** The override only checks the rule accounts; it skips the core checks (`is_storable`, `is_valued`, `valuation == "real_time"`, non-zero quantity), so a journal entry is created anyway.
- **Expected behavior:** Same checks as the core, plus the OBYC rule check.
- **Impact:** Unexpected stock entries for products valued manually.
- **Suggested fix:** Combine the core conditions with the OBYC rule check (without the core's location valuation account condition, which OBYC replaces).
- **Validation needed:** A test with a product with a valuation class in a manual-valuation category: no journal entry.

## OBYC-007 — P3: Smaller defects found while updating the consultant sheet

- **Status:** Open.
- **Error message without the location types:** `models/stock_move.py`, `_compute_transaction_key()` (line 132) uses `{source_usage}` / `{dest_usage}`, but `env._()` formats with `%`, so the message shows the braces literally. The `RedirectWarning` of `_get_rule_account` also shows the transaction key label in English.
- **Wrong examples in DESCRIPTION.md:** the "Typical Account Mappings" table (e.g. `stock_delivery` with source 371, destination 607, valuation 378) would generate Dr 378 / Cr 371. It also does not say that the destination account is ignored when the source account is set.
- **Storno on products without a valuation class:** the storno inversion in `_get_account_move_line_vals()` also applies to the core lines of products without a valuation class (rare case).
- **Rule title:** `_compute_display_name` shows the technical transaction key and "None" for an empty modifier.
- **Landed cost on goods partly delivered:** the core `stock_landed_costs` capitalizes only the part still in stock; the account of the cost line (408 in the demo) for the delivered part must be checked with the accountant. Core behavior, documented in the consultant sheet.

