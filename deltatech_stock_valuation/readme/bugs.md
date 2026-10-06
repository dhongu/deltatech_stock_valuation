# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## SV-001 — P2: Lines without a unit of measure are skipped by the recompute at posting

- **Status:** Fixed in 19.0.0.0.11. The posting branch of both models now uses
  `LEFT JOIN uom_uom ON COALESCE(l.product_uom_id, template.uom_id)`, like the full recompute.
  The whole line was lost before (quantity and value). Test: `test_known_bugs.test_sv001_*`.
- **Verification note:** `NULL` appears only on lines created by SQL, import or migration; the core
  fills in the unit on draft lines.
- **Location:** `models/product_valuation.py`, the branch with `product_ids` of the recompute (both models, around lines 337 and 752).
- **Trigger:** Post a journal entry with a stockable product line that has no `product_uom_id`.
- **Actual behavior:** The recompute run at posting joins `uom_uom` with `INNER JOIN` on `l.product_uom_id`, so the line is ignored. The full recompute (Recompute All) uses `COALESCE(l.product_uom_id, template.uom_id)` and counts it.
- **Expected behavior:** Both paths give the same quantity and value; a line without a unit uses the product unit.
- **Impact:** Product Valuation differs depending on which recompute ran last.
- **Suggested fix:** Use `LEFT JOIN ... COALESCE(l.product_uom_id, template.uom_id)` in the posting branch as well.
- **Validation needed:** A test that posts a line without a unit and compares the posting recompute with Recompute All.

## SV-002 — P2: Saving the settings updates journal items of all companies

- **Status:** Fixed in 19.0.0.0.11. The `UPDATE` now filters on `company_id` and also takes the lines
  with no area (`valuation_area_id IS NULL OR != ...`); it is written with `SQL()`. Test:
  `test_known_bugs.test_sv002_*`.
- **Verification note:** the impact was larger than described: the method runs not only when saving
  the settings, but at every full recompute and every step, including from the cron, so each company
  moved the lines of the others to its own area.
- **Location:** `models/res_company.py`, `set_stock_valuation_at_company_level()` (around line 50).
- **Trigger:** Save the valuation settings in a database with several companies.
- **Actual behavior:** `UPDATE account_move_line SET valuation_area_id = ... WHERE account_id IN ... AND valuation_area_id != ...` has no company filter. The condition `!=` also leaves out the lines with no area (NULL).
- **Expected behavior:** Only the lines of the current company are moved to its area, including the lines without an area.
- **Impact:** Lines of another company can be moved to the area of the current one. The lines without an area are only handled by the full recompute, through `COALESCE`.
- **Suggested fix:** Add `company_id = %(company_id)s` and `(valuation_area_id IS NULL OR valuation_area_id != ...)`.
- **Validation needed:** A test with two companies sharing an account code.

## SV-003 — P2: Background valuation refresh does not preserve the selected company

- **Status:** Fixed in 19.0.0.0.11. The start company is stored in
  `deltatech_stock_valuation.refresh_company_id` for the whole cycle (background start, resume and
  manual step 1); `_auto_refresh_step` runs every step with `sudo().with_company(<that company>)`
  and clears the parameter at the end. A manual step-by-step cycle started for one company is
  refused from another one (and while the background run is active); Reset clears the company.
  Tests: `test_known_bugs.test_sv003_*`.
- **Priority:** lowered from P1 to P2 at the verification of 2026-10-01: the history is derived data,
  rebuilt entirely from the journal entries, so no accounting data is lost; the persistent damage
  came from SV-002. The steps without company filter are tracked as SV-009.
- **Location:** models/res_config_settings.py, action_recompute_in_background() and start_auto_refresh(); models/product_valuation.py, _auto_refresh_step().
- **Trigger:** Start a background refresh while company B is selected, with the scheduler user defaulting to company A.
- **Actual behavior:** Start stores only global progress and notification user parameters. It does not store the selected company or set a company context for the cron. Refresh steps use the cron environment company, so the run recalculates A rather than B. The global step and product cursor can also be shared by manual refreshes in different companies.
- **Evidence:** Inspected the start methods, cron data/data.xml, global parameter names, and all refresh steps: the history deletion/rebuild selects self.env.company, and the cron code calls model._auto_refresh_step() without a company context. No database cron reproduction was run.
- **Impact:** The requested company is left with stale valuation while another company history is deleted and rebuilt. Switching companies between manual steps can execute an incomplete sequence for each company.
- **Suggested fix:** Persist and enforce a target company for the entire run, use with_company with the appropriate allowed-company context, and scope run progress/cursors by company or prevent mixed runs.
- **Validation needed:** Start from company B with scheduler default A; verify every step touches B only. Also test company switching during a manual run, stop/resume, and attempts to overlap refreshes.
- **Note:** merges the finding "background recompute runs on the default company of the cron user" from the consultant-sheet review with VALUATION-001 of a separate code review (2026-10-01).

- **Additional audit evidence:** Background-start methods persist global progress and notification user, but no target company. Cron code has no company context, and history deletion/rebuild uses `self.env.company`. The step and product cursor are also shared across manual company contexts.
- **Additional impact:** A refresh requested for company B can delete/rebuild company A history instead. Switching companies between manual steps can execute incomplete sequences. This deletion/rebuild risk is the reason for the P1 assessment in the consolidated audit.
- **Additional validation:** Start from B with scheduler default A; verify every step touches B only. Test company switching, stop/resume, and overlapping starts. No database cron reproduction was run.

## SV-004 — P3: Product Valuation rows can be added by hand and are lost at the next full recompute

- **Status:** Fixed in 19.0.0.0.11. The valuation table on the product is read-only (`readonly="1"`,
  `create="0"`); internal users only read `product.valuation` / `product.valuation.history`, and
  write access is given to `account.group_account_manager`. The incremental recompute at posting and
  the **Recompute Valuation** action on products run with `sudo()`, so any user who posts a stock
  entry still updates the valuation. Test: `test_known_bugs.test_sv004_*`.
- **Location:** product form (valuation table, **Add a line**); `security/ir.model.access.csv` gives full rights to internal users.
- **Trigger:** Add a row in the valuation table of a product, then run Recompute All.
- **Actual behavior:** The row is accepted, then deleted by the full recompute (only the rows that come from journal items are rebuilt).
- **Expected behavior:** The table is read-only, or the manual rows are refused.
- **Impact:** Corrections entered by hand silently disappear.
- **Suggested fix:** Make the table read-only (no create) and restrict write access to the accounting manager.
- **Validation needed:** A UI/access test.

## SV-005 — P3: USAGE.md and DESCRIPTION.md are out of date

- **Status:** Fixed in 19.0.0.0.11. `USAGE.md` rebuilt from the consultant sheet (menus under
  Inventory → Products, only Recompute All (Background) / Stop, area required on every stockable
  line, OBYC recommendation, value-only adjustments, reversal without storno, recompute per company,
  read-only table); `CONFIGURE.md` added. `DESCRIPTION.md` no longer describes the commented
  `_is_valuation_area_required` extension nor the old public method names. The consultant sheet
  drops the multi-company warnings fixed by SV-002/003/006.
- **Verification note:** the customer refund line in the `USAGE.md` table was correct as a net
  effect (`out_refund` counts as a negative out, i.e. + quantity); only the column classification
  differs.
- **Location:** `readme/USAGE.md`, `readme/DESCRIPTION.md`.
- **Actual behavior:** `USAGE.md` gives the menus under Inventory → Operations (they are under Inventory → Products), describes recompute buttons that are no longer in the settings, says the area is required only on the marked accounts (it is required on any line with a stockable product) and lists the customer refund as "+ in" (the code counts it as an out with a minus sign). `DESCRIPTION.md` describes the "smart validation" `_is_valuation_area_required`, which is commented out in `models/account_move_line.py`.
- **Expected behavior:** Both match `FISA_CONSULTANT.md` and the code.
- **Update 2026-10-01:** The consultant sheet was corrected after the accounting audit; `USAGE.md` must now also carry: the recommendation of `deltatech_obyc` for Romanian clients (without OBYC the stock accounts move only at invoicing), the warning against saving the settings or running Recompute All on multi-company databases (SV-002, SV-003), and the fact that a value-only adjustment changes the value and the average price (not the quantity). The reversal of stock entries without storno now cancels the quantity (`deltatech_valuation_area` 19.0.1.0.3); `USAGE.md` does not describe it either way.
- **Suggested fix:** Rebuild `USAGE.md` from the consultant sheet (`usage-din-fisa` agent) and correct `DESCRIPTION.md`.

## SV-006 — P3: New valuation rows use the environment currency instead of their explicit company

- **Status:** Fixed in 19.0.0.0.11. Both `get_valuation()` helpers write `currency_id` from the
  explicit company. The post-migration of 19.0.0.0.11 sets `currency_id` to the company currency on
  existing rows that differ. Test: `test_known_bugs.test_sv006_*`.
- **Priority:** lowered from P2 to P3: only the currency label was wrong (the amounts are in the
  company currency of the row) and the full recompute already restored it.
- **Location:** models/product_valuation.py, ProductValuation.get_valuation(), ProductValuationHistory.get_valuation(), and currency_id default; models/account_move.py, _recompute_valuation_keys().
- **Trigger:** From an environment whose current company is A/RON, post or recompute stock-accounting entries for allowed company B/EUR where valuation rows do not yet exist.
- **Actual behavior:** Both row helpers accept an explicit company_id and write B into the new row but omit currency_id and do not switch company. The inherited default sets currency_id from env.company A. Recomputed amounts are B company-currency amounts displayed with the A currency.
- **Evidence:** Executed the actual current-row helper with company_id=B and an environment-A currency default: the creation values had company B and default currency RON. Inspected the ORM field default, history helper, and accounting caller, which passes each line company without with_company. The mock reproduces value/default selection, not database accounting.
- **Impact:** Valuation and history rows display amounts under the wrong currency and can pollute monetary reporting across companies.
- **Suggested fix:** Resolve the explicit company before creating rows and use its currency_id, or create under with_company; review existing mismatched rows for migration.
- **Validation needed:** Current/history row creation for a non-current allowed company, posting mixed-company moves, and labels/amounts before and after a full rebuild.

## SV-007 — P3: Stock valuation server action calls removed public methods

- **Status:** Fixed in 19.0.0.0.11. The action calls `_recompute_all_amount()` on the history, then on
  the current valuation, is restricted to `base.group_system` (`group_ids` plus a check in the code)
  and `DESCRIPTION.md` shows the current names. Test: `test_known_bugs.test_sv007_*`.
- **Priority:** lowered from P2 to P3: the action has no binding and no menu; it is reachable only
  from Settings → Technical → Server Actions.
- **Location:** data/data.xml, action_product_valuation_history_recompute.
- **Trigger:** Run the installed Recompute All Stock Valuation server action directly or through an automation that references it.
- **Actual behavior:** Its Python code calls recompute_all_amount() on both valuation models. The current implementations expose _recompute_all_amount() instead; the public names are not defined in the local source. The action fails on the first call.
- **Evidence:** Inspected the manifest-loaded server action and searched method definitions/references across the suite. Settings and current usage documentation invoke the underscored methods. No database server-action execution was run.
- **Impact:** The installed server action cannot rebuild valuations and fails for callers using it.
- **Suggested fix:** Update the action to supported methods behind the appropriate administrative access checks, and align usage examples that still reference the old names.
- **Validation needed:** Execute the installed action as an authorized administrator and verify both history and current valuation recomputation; verify unauthorized execution is rejected.

## SV-008 — P3: The price of a row with zero final stock depends on the recompute path

- **Status:** Open (documented in `FISA_CONSULTANT.md`, section 6). Not part of the 2026-10-01 fix
  batch: choosing the single price rule is a functional decision (keep the previous price, or the
  last entry price from the lines with quantity in) still to be made.
- **Location:** `models/product_valuation.py`, `ProductValuation._recompute_amount()` (posting path) and the insert of `_recompute_all_amount()` (full recompute).
- **Trigger:** A product whose final stock in the last month is zero.
- **Actual behavior:** At posting, the price becomes `debit / quantity_in` of the last month (or the previous price when there were no entries); after Recompute All it becomes 0. `debit` also includes customer refunds (an `out_refund` debits the stock account but its quantity is counted as a negative out, not as an in) and value-only adjustments, so `debit / quantity_in` can be distorted.
- **Expected behavior:** The same price on both paths, computed only from the entries that carry a quantity in.
- **Impact:** With Use Valuation Area Price, an out for such a row is valued at the standard price after a full recompute and at a possibly distorted price after a posting.
- **Suggested fix:** Use one rule on both paths (keep the previous price, or the last entry price computed from the lines with quantity in only).
- **Validation needed:** A test with an in, an out of the whole stock and a customer refund in the same month, comparing the price after posting and after Recompute All.

## SV-009 — P2: Steps 2, 3, 4 and 6 of the full recompute are not scoped to the company

- **Status:** Fixed in 19.0.0.0.11. Found at the verification of SV-003 (2026-10-01).
- **Location:** `models/product_valuation.py`, `ProductValuationHistory._recompute_all_amount()`.
- **Actual behavior:** step 2 inserted the history of the posted lines of **all** companies (the
  sub-select without products had no `m.company_id` filter) and could fail with a unique violation
  on the existing history of another company (masked by SV-002, which first moved those lines to the
  current area); step 3 cross-joined the `(product, account)` pairs of the whole history, so it added
  products of other companies to the current one; step 4 updated the final balance of other
  companies' rows; step 6 deleted empty rows by area only.
- **Fix:** step 2 passes `company_id` to `_get_sql_select()` / `_get_sql_sub_select()`; steps 3, 4
  and 6 filter on the company; steps 3 and 6 are written with `SQL()`.
  Step 1 now deletes the whole history of the company. The post-migration of 19.0.0.0.11
  (`_cleanup_cross_company_rows()`) repairs the data left by the old version: stock journal items on
  the area of another company go back to their company area, and valuation / history rows on the
  area of another company are removed (found by the accounting review, which noted that
  `l10n_ro_stock_provision` sums the history of a company over all areas).
- **Test:** `test_known_bugs.test_sv003_full_recompute_steps_are_scoped_to_company`.

## Review limitations

SV-001..005 and SV-008 come from checking the consultant sheet against the code; SV-001, SV-002 and the
server action of SV-007 were checked in the source. SV-003, SV-006 and SV-007 come from a separate
code review (local source inspection and isolated reproductions, no database-backed integration
test). SV-001..007 were verified on `origin/19.0` on 2026-10-01 and fixed in 19.0.0.0.11, each with
a database-backed regression test in `tests/test_known_bugs.py` that failed before the fix; SV-009
was found during that verification. SV-008 remains open.

## Reverification — 2026-10-01

Compared the current local `19.0` source with the original audit snapshot. Repository HEAD: `ccfe68b`. This pass verifies source changes; module integration tests and upgrade migrations were not executed on an Odoo database.

- **SV-003 — fixed in source:** the changed implementation addresses the originally documented failure. See the fix description and regression tests above. Deployment and database upgrade are outside this verification.
- **SV-006 — fixed in source:** the changed implementation addresses the originally documented failure. See the fix description and regression tests above. Deployment and database upgrade are outside this verification.
- **SV-007 — fixed in source:** the changed implementation addresses the originally documented failure. See the fix description and regression tests above. Deployment and database upgrade are outside this verification.

## SV-010 — Area-price valuation fails for products using OBYC account determination

- **Priority:** P1
- **Status:** Open (2026-10-02).
- **Source:** `models/stock_move.py, _get_valuation_area_price; deltatech_obyc/models/product_template.py, _get_product_accounts`.
- **Trigger:** Enable Use Valuation Area Price on an AVCO category and assign an OBYC valuation class to its product, then validate an outgoing move.
- **Observed behavior:** The area-price helper calls get_product_accounts without transaction_key or OBYC rule context. The OBYC override rejects such calls, raising Transaction key is not defined before the area-price query. Outgoing validation can fail rather than use the configured valuation.
- **Evidence:** Executed the actual extracted helpers with super/environment shims; the call raises UserError. Core get_product_accounts delegates to _get_product_accounts. Reproduction: audit_coverage/reproductions/valuation_context.py; no database posting.
- **Suggested fix / regression check:** Resolve the valuation account through the OBYC rule for the move, or supply the full rule context; test both modules installed together.

## SV-011 — Resetting refresh progress can redirect an active background run to the cron company

- **Priority:** P2
- **Status:** Open (2026-10-02).
- **Source:** `models/res_config_settings.py, reset_refresh_valuation_step; models/product_valuation.py, _auto_refresh_step`.
- **Trigger:** While a background cycle for company B is active, an administrator calls the public reset method through RPC or a custom action. The standard manual reset button is currently commented out.
- **Observed behavior:** Reset clears the saved company and resets step/cursor without checking or disabling the cron. Its next invocation falls back to the cron environment company A and starts step 1 there. This bypasses the company guard used by manual stepping.
- **Evidence:** Executed the extracted reset and observed cleared company/progress; inspected active-cron handling and fallback in _auto_refresh_step. Source/mocked evidence only, no cron database execution.
- **Suggested fix / regression check:** Reject reset while a cycle is running, or stop it atomically before clearing the run identity; test reset/resume with different initiating and scheduler companies.

## SV-012 — Valuation rows are readable across unauthorized companies

- **Priority:** P1
- **Status:** Open (2026-10-02).
- **Source:** `security/ir.model.access.csv; security/security.xml; models/product_valuation.py`.
- **Trigger:** An internal user limited to company A searches or reads product.valuation or product.valuation.history while company B has valuation records.
- **Observed behavior:** Both models grant base.group_user read access. The manifest-loaded security XML is empty and there are no company record rules in this suite for these newly defined models. A company_id field or company default alone does not filter searches, so valuation quantities, costs and history from B are exposed. Accounting managers also receive unrestricted write permissions.
- **Evidence:** Inspected model definitions, ACL CSVs, manifests and all suite security declarations. No database ACL reproduction; an unrelated installed extension could add its own rules.
- **Suggested fix / regression check:** Add company record rules for both models using allowed_company_ids and verify read/write isolation through ORM and RPC, including shared products.
