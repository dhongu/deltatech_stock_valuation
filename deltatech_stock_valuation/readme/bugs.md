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

## SV-003 — P1: Background valuation refresh does not preserve the selected company

- **Status:** Open.
- **Location:** models/res_config_settings.py, action_recompute_in_background() and start_auto_refresh(); models/product_valuation.py, _auto_refresh_step().
- **Trigger:** Start a background refresh while company B is selected, with the scheduler user defaulting to company A.
- **Actual behavior:** Start stores only global progress and notification user parameters. It does not store the selected company or set a company context for the cron. Refresh steps use the cron environment company, so the run recalculates A rather than B. The global step and product cursor can also be shared by manual refreshes in different companies.
- **Evidence:** Inspected the start methods, cron data/data.xml, global parameter names, and all refresh steps: the history deletion/rebuild selects self.env.company, and the cron code calls model._auto_refresh_step() without a company context. No database cron reproduction was run.
- **Impact:** The requested company is left with stale valuation while another company history is deleted and rebuilt. Switching companies between manual steps can execute an incomplete sequence for each company.
- **Suggested fix:** Persist and enforce a target company for the entire run, use with_company with the appropriate allowed-company context, and scope run progress/cursors by company or prevent mixed runs.
- **Validation needed:** Start from company B with scheduler default A; verify every step touches B only. Also test company switching during a manual run, stop/resume, and attempts to overlap refreshes.
- **Note:** merges the finding "background recompute runs on the default company of the cron user" from the consultant-sheet review with VALUATION-001 of a separate code review (2026-10-01).

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

## SV-006 — P2: New valuation rows use the environment currency instead of their explicit company

- **Status:** Open.
- **Location:** models/product_valuation.py, ProductValuation.get_valuation(), ProductValuationHistory.get_valuation(), and currency_id default; models/account_move.py, _recompute_valuation_keys().
- **Trigger:** From an environment whose current company is A/RON, post or recompute stock-accounting entries for allowed company B/EUR where valuation rows do not yet exist.
- **Actual behavior:** Both row helpers accept an explicit company_id and write B into the new row but omit currency_id and do not switch company. The inherited default sets currency_id from env.company A. Recomputed amounts are B company-currency amounts displayed with the A currency.
- **Evidence:** Executed the actual current-row helper with company_id=B and an environment-A currency default: the creation values had company B and default currency RON. Inspected the ORM field default, history helper, and accounting caller, which passes each line company without with_company. The mock reproduces value/default selection, not database accounting.
- **Impact:** Valuation and history rows display amounts under the wrong currency and can pollute monetary reporting across companies.
- **Suggested fix:** Resolve the explicit company before creating rows and use its currency_id, or create under with_company; review existing mismatched rows for migration.
- **Validation needed:** Current/history row creation for a non-current allowed company, posting mixed-company moves, and labels/amounts before and after a full rebuild.

## SV-007 — P2: Stock valuation server action calls removed public methods

- **Status:** Open.
- **Location:** data/data.xml, action_product_valuation_history_recompute.
- **Trigger:** Run the installed Recompute All Stock Valuation server action directly or through an automation that references it.
- **Actual behavior:** Its Python code calls recompute_all_amount() on both valuation models. The current implementations expose _recompute_all_amount() instead; the public names are not defined in the local source. The action fails on the first call.
- **Evidence:** Inspected the manifest-loaded server action and searched method definitions/references across the suite. Settings and current usage documentation invoke the underscored methods. No database server-action execution was run.
- **Impact:** The installed server action cannot rebuild valuations and fails for callers using it.
- **Suggested fix:** Update the action to supported methods behind the appropriate administrative access checks, and align usage examples that still reference the old names.
- **Validation needed:** Execute the installed action as an authorized administrator and verify both history and current valuation recomputation; verify unauthorized execution is rejected.

## Review limitations

SV-001..005 come from checking the consultant sheet against the code; SV-001, SV-002 and the
server action of SV-007 were checked in the source. SV-003, SV-006 and SV-007 come from a separate
code review (local source inspection and isolated reproductions, no database-backed integration
test). No fixes have been applied.
