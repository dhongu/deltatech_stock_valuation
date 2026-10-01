# Known bugs

Review date: 2026-10-01. Target version: Odoo 20.

The IDs come from the 19.0 review (`readme/bugs.md` on 19.0); each entry was re-checked against
the 20.0 code. Line numbers refer to the 20.0 branch.

## SV-001 — P2: Lines without a unit of measure are skipped by the recompute at posting

- **Status:** Fixed in 20.0.0.0.10. The posting branch of both models now uses
  `LEFT JOIN uom_uom ON COALESCE(l.product_uom_id, template.uom_id)`, like the full recompute.
  The whole line was lost before (quantity and value). Test: `test_known_bugs.test_sv001_*`.
- **Verification note:** `NULL` appears only on lines created by SQL, import or migration; the core
  fills in the unit on draft lines.
- **Location:** `models/product_valuation.py`, the branch with `product_ids` of `_get_sql_sub_select()` in both models (lines 336-337 for `product.valuation`, 751-752 for `product.valuation.history`).
- **Trigger:** Post a journal entry with a stockable product line that has no `product_uom_id`.
- **Actual behavior:** The recompute run at posting joins `uom_uom` with `INNER JOIN` on `l.product_uom_id`, so the line is ignored. The full recompute (Recompute All) uses `COALESCE(l.product_uom_id, template.uom_id)` (lines 318, 732, 1035) and counts it.
- **Evidence (20.0):** Reproduced in an Odoo shell on a 20.0 database: a line of 5 units / 50.00 without a unit gave quantity 0 / amount 0 after posting, and 5 / 50.00 after Recompute All.
- **Expected behavior:** Both paths give the same quantity and value; a line without a unit uses the product unit.
- **Impact:** Product Valuation differs depending on which recompute ran last.
- **Suggested fix:** Use `LEFT JOIN ... COALESCE(l.product_uom_id, template.uom_id)` in the posting branch as well.
- **Validation needed:** A test that posts a line without a unit and compares the posting recompute with Recompute All.

## SV-002 — P2: Saving the settings updates journal items of all companies

- **Status:** Fixed in 20.0.0.0.10. The `UPDATE` now filters on `company_id` and also takes the lines
  with no area (`valuation_area_id IS NULL OR != ...`); it is written with `SQL()`. Test:
  `test_known_bugs.test_sv002_*`.
- **Verification note:** the impact was larger than described: the method runs not only when saving
  the settings, but at every full recompute and every step, including from the cron, so each company
  moved the lines of the others to its own area.
- **Location:** `models/res_company.py`, `set_stock_valuation_at_company_level()` (lines 48-54).
- **Trigger:** Save the valuation settings in a database with several companies.
- **Actual behavior:** `UPDATE account_move_line SET valuation_area_id = ... WHERE account_id IN ... AND valuation_area_id != ...` has no company filter. The condition `!=` also leaves out the lines with no area (NULL).
- **Expected behavior:** Only the lines of the current company are moved to its area, including the lines without an area.
- **Impact:** Lines of another company can be moved to the area of the current one. The lines without an area are only handled by the full recompute, through `COALESCE`.
- **Suggested fix:** Add `company_id = %(company_id)s` and `(valuation_area_id IS NULL OR valuation_area_id != ...)`.
- **Validation needed:** A test with two companies sharing an account code.

## SV-003 — P2: Background valuation refresh does not preserve the selected company

- **Status:** Fixed in 20.0.0.0.10. The start company is stored in
  `deltatech_stock_valuation.refresh_company_id` for the whole cycle (background start, resume and
  manual step 1); `_auto_refresh_step` runs every step with `sudo().with_company(<that company>)`
  and clears the parameter at the end. A manual step-by-step cycle started for one company is
  refused from another one (and while the background run is active); Reset clears the company.
  Tests: `test_known_bugs.test_sv003_*`.
- **Priority:** lowered from P1 to P2 at the verification of 2026-10-01 (19.0): the history is derived data,
  rebuilt entirely from the journal entries, so no accounting data is lost; the persistent damage
  came from SV-002. The steps without company filter are tracked as SV-009.
- **Location:** `models/res_config_settings.py`, `action_recompute_in_background()` (line 161) and `start_auto_refresh()` (line 193); `models/product_valuation.py`, `_auto_refresh_step()` (line 1184), `_recompute_all_amount()` (lines 865-872) and `_recompute_step5_batch()` (lines 1136-1140); `data/data.xml`, cron `ir_cron_auto_refresh_valuation`.
- **Trigger:** Start a background refresh while company B is selected, with the scheduler user defaulting to company A.
- **Actual behavior:** Start stores only the global step and the notification user (`_PARAM_STEP`, `_PARAM_NOTIFY_UID`, `ir.config_parameter` keys at lines 17-22 of `product_valuation.py`). It does not store the selected company or set a company context for the cron. The refresh steps use `self.env.company` of the cron environment, so the run deletes and rebuilds the history of A rather than B. The global step and product cursor are also shared by manual refreshes in different companies.
- **Evidence (20.0):** Inspected the start methods, the cron (`model._auto_refresh_step()` without a company context) and all refresh steps; the code is unchanged from 19.0 apart from the typed `ir.config_parameter` API. No database cron reproduction was run.
- **Impact:** The requested company is left with stale valuation while another company's history is deleted and rebuilt. Switching companies between manual steps can execute an incomplete sequence for each company.
- **Suggested fix:** Persist and enforce a target company for the entire run, use `with_company` with the appropriate allowed-company context, and scope run progress/cursors by company or prevent mixed runs.
- **Validation needed:** Start from company B with scheduler default A; verify every step touches B only. Also test company switching during a manual run, stop/resume, and attempts to overlap refreshes.

## SV-004 — P3: Product Valuation rows can be added by hand and are lost at the next full recompute

- **Status:** Fixed in 20.0.0.0.10. The valuation table on the product is read-only (`readonly="1"`,
  `create="0"`); internal users only read `product.valuation` / `product.valuation.history`, and
  write access is given to `account.group_account_manager`. The incremental recompute at posting and
  the **Recompute Valuation** action on products run with `sudo()`, so any user who posts a stock
  entry still updates the valuation. Test: `test_known_bugs.test_sv004_*`.
- **Location:** `views/product_template_views.xml` (line 12, `<list editable="bottom" delete="0">` on `product_valuation_ids`); `security/ir.access.csv` gives `crud` on both valuation models to `base.group_user`.
- **Trigger:** Add a row in the valuation table of a product (tab **Accounting**, **Add a line**), then run Recompute All.
- **Actual behavior:** The row is accepted, then deleted by the full recompute (only the rows that come from journal items are rebuilt).
- **Expected behavior:** The table is read-only, or the manual rows are refused.
- **Impact:** Corrections entered by hand silently disappear.
- **Suggested fix:** Make the table read-only (no create) and restrict write access to the accounting manager (`ir.access` rows with operation `r` for internal users).
- **Validation needed:** A UI/access test.

## SV-005 — P3: USAGE.md and DESCRIPTION.md are out of date

- **Status:** Fixed in 20.0.0.0.10. `USAGE.md` rebuilt from the consultant sheet (menus under
  Inventory → Products, only Recompute All (Background) / Stop, area required on every stockable
  line, OBYC recommendation, value-only adjustments, reversal without storno, recompute per company,
  read-only table); `CONFIGURE.md` added. `DESCRIPTION.md` no longer describes the commented
  `_is_valuation_area_required` extension nor the old public method names. The consultant sheet
  drops the multi-company warnings fixed by SV-002/003/006.
- **Verification note:** the customer refund line in the `USAGE.md` table was correct as a net
  effect (`out_refund` counts as a negative out, i.e. + quantity); only the column classification
  differs.
- **Location:** `readme/USAGE.md`, `readme/DESCRIPTION.md`.
- **Actual behavior:** `USAGE.md` gives the menus under Inventory → Operations (lines 53-55; they are under Inventory → Products, `stock.menu_stock_inventory_control`), describes the manual recompute buttons (line 80 and following) that are commented out in `views/res_config_settings_views.xml`, says the area is required only on the marked accounts (line 24; it is required on any line with a stockable product, `deltatech_valuation_area`) and lists the customer refund as "+ in" (line 49; the code counts it as an out with a minus sign). `DESCRIPTION.md` describes the "smart validation" `_is_valuation_area_required` (lines 12 and 24), which is commented out in `models/account_move_line.py`, and recommends the server-side calls `recompute_all_amount()` (lines 31-32), which do not exist (see SV-007). Neither file mentions the Odoo 20 setting *Keep move value on retroactive recompute*.
- **Expected behavior:** Both match `FISA_CONSULTANT.md` and the code.
- **Suggested fix:** Rebuild `USAGE.md` from the consultant sheet (`usage-din-fisa` agent) and correct `DESCRIPTION.md`.
- **Update 2026-10-01:** The consultant sheet was corrected after the accounting audit (20.0.0.0.11).
  `USAGE.md` already carries the recommendation of `deltatech_obyc` for Romanian clients, the
  value-only adjustment (value and average price change, not the quantity) and the reversal with
  and without storno; the multi-company warning of the 19.0 sheet is not needed on 20.0, where
  SV-002 and SV-003 are fixed. The reversal of stock entries now cancels the quantity
  (`deltatech_valuation_area` 20.0.1.0.5); `USAGE.md` does not mention the zero-value lines with
  storno nor the month-end procedure without OBYC, which stay in the consultant sheet.

## SV-006 — P3: New valuation rows use the environment currency instead of their explicit company

- **Status:** Fixed in 20.0.0.0.10. Both `get_valuation()` helpers write `currency_id` from the
  explicit company. The post-migration of 20.0.0.0.10 sets `currency_id` to the company currency on
  existing rows that differ. Test: `test_known_bugs.test_sv006_*`.
- **Priority:** lowered from P2 to P3: only the currency label was wrong (the amounts are in the
  company currency of the row) and the full recompute already restored it.
- **Location:** `models/product_valuation.py`, `currency_id` default (line 60), `ProductValuation.get_valuation()` (lines 72-102) and `ProductValuationHistory.get_valuation()` (lines 471-530); `models/account_move.py`, `_recompute_valuation_keys()` (lines 33-53).
- **Trigger:** From an environment whose current company is A, post or recompute stock-accounting entries for an allowed company B with another currency, where valuation rows do not yet exist.
- **Actual behavior:** Both row helpers accept an explicit `company_id` and write B into the new row but omit `currency_id` and do not switch company. The default sets `currency_id` from `env.company` (A). Recomputed amounts are B company-currency amounts displayed with the A currency.
- **Evidence (20.0):** Reproduced in an Odoo shell on a 20.0 database: `product.valuation.get_valuation(..., company_id=B)` with B in EUR, called from company A in USD, created a row with company B and currency USD.
- **Impact:** Valuation and history rows display amounts under the wrong currency and can pollute monetary reporting across companies.
- **Suggested fix:** Resolve the explicit company before creating rows and use its `currency_id`, or create under `with_company`; review existing mismatched rows for migration.
- **Validation needed:** Current/history row creation for a non-current allowed company, posting mixed-company moves, and labels/amounts before and after a full rebuild.

## SV-007 — P3: Stock valuation server action calls removed public methods

- **Status:** Fixed in 20.0.0.0.10. The action calls `_recompute_all_amount()` on the history, then on
  the current valuation, is restricted to `base.group_system` (`group_ids` plus a check in the code)
  and `DESCRIPTION.md` shows the current names. Test: `test_known_bugs.test_sv007_*`.
- **Priority:** lowered from P2 to P3: the action has no binding and no menu; it is reachable only
  from Settings → Technical → Server Actions.
- **Location:** `data/data.xml`, `action_product_valuation_history_recompute` (lines 4-12).
- **Trigger:** Run the installed *Recompute All Stock Valuation* server action directly or through an automation that references it.
- **Actual behavior:** Its Python code calls `recompute_all_amount()` on both valuation models. The implementations expose only `_recompute_all_amount()`; the public names are not defined anywhere in the suite. The action fails on the first call.
- **Evidence (20.0):** Executed the installed action in an Odoo shell on a 20.0 database: `ValueError: AttributeError("'product.valuation.history' object has no attribute 'recompute_all_amount'")`.
- **Impact:** The installed server action cannot rebuild valuations and fails for callers using it.
- **Suggested fix:** Update the action to supported methods behind the appropriate administrative access checks, and align `readme/DESCRIPTION.md` (see SV-005).
- **Validation needed:** Execute the installed action as an authorized administrator and verify both history and current valuation recomputation; verify unauthorized execution is rejected.

## SV-008 — P3: The price of a row with zero final stock depends on the recompute path

- **Status:** Open (documented in `FISA_CONSULTANT.md`, section 6). Found on 19.0 when checking the
  consultant sheet against the code; the 20.0 code is the same.
- **Location:** `models/product_valuation.py`, `ProductValuation._recompute_amount()` (posting path,
  lines 189-193) and the insert of `ProductValuation._recompute_all_amount()` (full recompute,
  lines 435-437).
- **Trigger:** A product whose final stock in the last month is zero.
- **Actual behavior:** At posting, the price becomes `debit / quantity_in` of the last month (or the previous price when there were no entries); after Recompute All it becomes 0. `debit` also includes customer refunds (an `out_refund` debits the stock account but its quantity is counted as a negative out, not as an in, `_get_quantity_in_out_sql()`) and value-only adjustments, so `debit / quantity_in` can be distorted.
- **Expected behavior:** The same price on both paths, computed only from the entries that carry a quantity in.
- **Impact:** With Use Valuation Area Price, an out for such a row is valued at the standard price after a full recompute and at a possibly distorted price after a posting.
- **Suggested fix:** Use one rule on both paths (keep the previous price, or the last entry price computed from the lines with quantity in only).
- **Validation needed:** A test with an in, an out of the whole stock and a customer refund in the same month, comparing the price after posting and after Recompute All.

## SV-009 — P2: Steps 2, 3, 4 and 6 of the full recompute are not scoped to the company

- **Status:** Fixed in 20.0.0.0.10. Found at the verification of SV-003 (2026-10-01).
- **Location:** `models/product_valuation.py`, `ProductValuationHistory._recompute_all_amount()`.
- **Actual behavior:** step 2 inserted the history of the posted lines of **all** companies (the
  sub-select without products had no `m.company_id` filter) and could fail with a unique violation
  on the existing history of another company (masked by SV-002, which first moved those lines to the
  current area); step 3 cross-joined the `(product, account)` pairs of the whole history, so it added
  products of other companies to the current one; step 4 updated the final balance of other
  companies' rows; step 6 deleted empty rows by area only.
- **Fix:** step 2 passes `company_id` to `_get_sql_select()` / `_get_sql_sub_select()`; steps 3, 4
  and 6 filter on the company; steps 3 and 6 are written with `SQL()`.
  Step 1 now deletes the whole history of the company. The post-migration of 20.0.0.0.10
  (`_cleanup_cross_company_rows()`) repairs the data left by the old version: stock journal items on
  the area of another company go back to their company area, and valuation / history rows on the
  area of another company are removed (found by the accounting review, which noted that
  `l10n_ro_stock_provision` sums the history of a company over all areas).
- **Test:** `test_known_bugs.test_sv003_full_recompute_steps_are_scoped_to_company`.

## Review limitations

SV-001, SV-006 and SV-007 were reproduced in an Odoo shell on a 20.0 database (changes rolled
back). SV-002, SV-003, SV-004 and SV-005 were confirmed by reading the 20.0 source; no
multi-company or cron reproduction was run. All of them (and SV-009) were fixed in 20.0.0.0.10,
ported from 19.0.0.0.11, each with a database-backed regression test in `tests/test_known_bugs.py`.
SV-008 comes from checking the consultant sheet against the code (19.0 audit) and was re-checked by
reading the 20.0 source; it is not fixed.
