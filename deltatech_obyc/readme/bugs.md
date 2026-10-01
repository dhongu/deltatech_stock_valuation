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
