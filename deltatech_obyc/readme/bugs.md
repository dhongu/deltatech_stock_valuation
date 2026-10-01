# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## OBYC-001 — P1: Invoice product lines get the valuation account instead of the income/expense account

- **Status:** Open.
- **Location:** `models/account_move_line.py`, `_compute_account_id()`.
- **Trigger:** Create a customer invoice (or a vendor bill) with a product that has an OBYC valuation class.
- **Actual behavior:** The product line is posted on `acc_valuation_id` of the `stock_income` rule (customer invoice) or of the `stock_receipt` rule (vendor bill). The account is chosen from `line.debit` / `line.credit`, but when the line is created the compute runs before the balance is set, so both are 0 and the fallback `acc_valuation_id` is kept.
- **Expected behavior:** The customer invoice line is posted on the income account of the rule (`acc_dest_id` for a credit line), the vendor bill line on the GR/IR account (`acc_src_id` for a debit line).
- **Impact:** Revenue from customer invoices ends up on the stock valuation account; vendor bills debit the stock account instead of the GR/IR account. The entry is balanced, so nothing fails.
- **Evidence:** The same code exists on 18.0, 19.0 and 20.0. `tests/test_account_move_line.py` and `tests/test_obyc_entries.py` call `_compute_account_id()` again after the invoice is created, which hides the problem.
- **Suggested fix:** Choose the account from the document type instead of the line balance (sale → `acc_dest_id`, purchase → `acc_src_id`), and decide which account the credit notes (`out_refund` / `in_refund`) use.
- **Validation needed:** A test that posts a customer invoice and a vendor bill without recomputing the account, and checks the account of the product line; the same for credit notes.

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
