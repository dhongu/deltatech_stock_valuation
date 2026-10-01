# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## SV-001 — P2: Lines without a unit of measure are skipped by the recompute at posting

- **Status:** Open.
- **Location:** `models/product_valuation.py`, the branch with `product_ids` of the recompute (both models, around lines 337 and 752).
- **Trigger:** Post a journal entry with a stockable product line that has no `product_uom_id`.
- **Actual behavior:** The recompute run at posting joins `uom_uom` with `INNER JOIN` on `l.product_uom_id`, so the line is ignored. The full recompute (Recompute All) uses `COALESCE(l.product_uom_id, template.uom_id)` and counts it.
- **Expected behavior:** Both paths give the same quantity and value; a line without a unit uses the product unit.
- **Impact:** Product Valuation differs depending on which recompute ran last.
- **Suggested fix:** Use `LEFT JOIN ... COALESCE(l.product_uom_id, template.uom_id)` in the posting branch as well.
- **Validation needed:** A test that posts a line without a unit and compares the posting recompute with Recompute All.

## SV-002 — P2: Saving the settings updates journal items of all companies

- **Status:** Open.
- **Location:** `models/res_company.py`, `set_stock_valuation_at_company_level()` (around line 50).
- **Trigger:** Save the valuation settings in a database with several companies.
- **Actual behavior:** `UPDATE account_move_line SET valuation_area_id = ... WHERE account_id IN ... AND valuation_area_id != ...` has no company filter. The condition `!=` also leaves out the lines with no area (NULL).
- **Expected behavior:** Only the lines of the current company are moved to its area, including the lines without an area.
- **Impact:** Lines of another company can be moved to the area of the current one. The lines without an area are only handled by the full recompute, through `COALESCE`.
- **Suggested fix:** Add `company_id = %(company_id)s` and `(valuation_area_id IS NULL OR valuation_area_id != ...)`.
- **Validation needed:** A test with two companies sharing an account code.

## SV-003 — P3: The background recompute runs on the default company of the cron user

- **Status:** Open.
- **Location:** `models/product_valuation.py`, `_recompute_all_amount()` (`self.env.company`).
- **Trigger:** Start Recompute All (Background) in a multi-company database.
- **Actual behavior:** The scheduled action recomputes only the default company of its user.
- **Expected behavior:** The company that started the recompute, or all companies that use the module.
- **Impact:** The other companies keep stale valuations.
- **Suggested fix:** Pass the company to the scheduled job, or loop over the companies with `with_company()`.
- **Validation needed:** A multi-company test of the background recompute.

## SV-004 — P3: Product Valuation rows can be added by hand and are lost at the next full recompute

- **Status:** Open.
- **Location:** product form (valuation table, **Add a line**); `security/ir.model.access.csv` gives full rights to internal users.
- **Trigger:** Add a row in the valuation table of a product, then run Recompute All.
- **Actual behavior:** The row is accepted, then deleted by the full recompute (only the rows that come from journal items are rebuilt).
- **Expected behavior:** The table is read-only, or the manual rows are refused.
- **Impact:** Corrections entered by hand silently disappear.
- **Suggested fix:** Make the table read-only (no create) and restrict write access to the accounting manager.
- **Validation needed:** A UI/access test.

## SV-005 — P3: USAGE.md and DESCRIPTION.md are out of date

- **Status:** Open.
- **Location:** `readme/USAGE.md`, `readme/DESCRIPTION.md`.
- **Actual behavior:** `USAGE.md` gives the menus under Inventory → Operations (they are under Inventory → Products), describes recompute buttons that are no longer in the settings, says the area is required only on the marked accounts (it is required on any line with a stockable product) and lists the customer refund as "+ in" (the code counts it as an out with a minus sign). `DESCRIPTION.md` describes the "smart validation" `_is_valuation_area_required`, which is commented out in `models/account_move_line.py`.
- **Expected behavior:** Both match `FISA_CONSULTANT.md` and the code.
- **Suggested fix:** Rebuild `USAGE.md` from the consultant sheet (`usage-din-fisa` agent) and correct `DESCRIPTION.md`.
