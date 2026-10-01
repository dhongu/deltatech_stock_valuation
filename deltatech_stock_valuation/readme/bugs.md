# Known bugs

Review date: 2026-10-01. Target version: Odoo 20.

The IDs come from the 19.0 review (`readme/bugs.md` on 19.0); each entry was re-checked against
the 20.0 code. Line numbers refer to the 20.0 branch.

## SV-001 — P2: Lines without a unit of measure are skipped by the recompute at posting

- **Status:** Open.
- **Location:** `models/product_valuation.py`, the branch with `product_ids` of `_get_sql_sub_select()` in both models (lines 336-337 for `product.valuation`, 751-752 for `product.valuation.history`).
- **Trigger:** Post a journal entry with a stockable product line that has no `product_uom_id`.
- **Actual behavior:** The recompute run at posting joins `uom_uom` with `INNER JOIN` on `l.product_uom_id`, so the line is ignored. The full recompute (Recompute All) uses `COALESCE(l.product_uom_id, template.uom_id)` (lines 318, 732, 1035) and counts it.
- **Evidence (20.0):** Reproduced in an Odoo shell on a 20.0 database: a line of 5 units / 50.00 without a unit gave quantity 0 / amount 0 after posting, and 5 / 50.00 after Recompute All.
- **Expected behavior:** Both paths give the same quantity and value; a line without a unit uses the product unit.
- **Impact:** Product Valuation differs depending on which recompute ran last.
- **Suggested fix:** Use `LEFT JOIN ... COALESCE(l.product_uom_id, template.uom_id)` in the posting branch as well.
- **Validation needed:** A test that posts a line without a unit and compares the posting recompute with Recompute All.

## SV-002 — P2: Saving the settings updates journal items of all companies

- **Status:** Open.
- **Location:** `models/res_company.py`, `set_stock_valuation_at_company_level()` (lines 48-54).
- **Trigger:** Save the valuation settings in a database with several companies.
- **Actual behavior:** `UPDATE account_move_line SET valuation_area_id = ... WHERE account_id IN ... AND valuation_area_id != ...` has no company filter. The condition `!=` also leaves out the lines with no area (NULL).
- **Expected behavior:** Only the lines of the current company are moved to its area, including the lines without an area.
- **Impact:** Lines of another company can be moved to the area of the current one. The lines without an area are only handled by the full recompute, through `COALESCE`.
- **Suggested fix:** Add `company_id = %(company_id)s` and `(valuation_area_id IS NULL OR valuation_area_id != ...)`.
- **Validation needed:** A test with two companies sharing an account code.

## SV-003 — P1: Background valuation refresh does not preserve the selected company

- **Status:** Open.
- **Location:** `models/res_config_settings.py`, `action_recompute_in_background()` (line 161) and `start_auto_refresh()` (line 193); `models/product_valuation.py`, `_auto_refresh_step()` (line 1184), `_recompute_all_amount()` (lines 865-872) and `_recompute_step5_batch()` (lines 1136-1140); `data/data.xml`, cron `ir_cron_auto_refresh_valuation`.
- **Trigger:** Start a background refresh while company B is selected, with the scheduler user defaulting to company A.
- **Actual behavior:** Start stores only the global step and the notification user (`_PARAM_STEP`, `_PARAM_NOTIFY_UID`, `ir.config_parameter` keys at lines 17-22 of `product_valuation.py`). It does not store the selected company or set a company context for the cron. The refresh steps use `self.env.company` of the cron environment, so the run deletes and rebuilds the history of A rather than B. The global step and product cursor are also shared by manual refreshes in different companies.
- **Evidence (20.0):** Inspected the start methods, the cron (`model._auto_refresh_step()` without a company context) and all refresh steps; the code is unchanged from 19.0 apart from the typed `ir.config_parameter` API. No database cron reproduction was run.
- **Impact:** The requested company is left with stale valuation while another company's history is deleted and rebuilt. Switching companies between manual steps can execute an incomplete sequence for each company.
- **Suggested fix:** Persist and enforce a target company for the entire run, use `with_company` with the appropriate allowed-company context, and scope run progress/cursors by company or prevent mixed runs.
- **Validation needed:** Start from company B with scheduler default A; verify every step touches B only. Also test company switching during a manual run, stop/resume, and attempts to overlap refreshes.

## SV-004 — P3: Product Valuation rows can be added by hand and are lost at the next full recompute

- **Status:** Open.
- **Location:** `views/product_template_views.xml` (line 12, `<list editable="bottom" delete="0">` on `product_valuation_ids`); `security/ir.access.csv` gives `crud` on both valuation models to `base.group_user`.
- **Trigger:** Add a row in the valuation table of a product (tab **Accounting**, **Add a line**), then run Recompute All.
- **Actual behavior:** The row is accepted, then deleted by the full recompute (only the rows that come from journal items are rebuilt).
- **Expected behavior:** The table is read-only, or the manual rows are refused.
- **Impact:** Corrections entered by hand silently disappear.
- **Suggested fix:** Make the table read-only (no create) and restrict write access to the accounting manager (`ir.access` rows with operation `r` for internal users).
- **Validation needed:** A UI/access test.

## SV-005 — P3: USAGE.md and DESCRIPTION.md are out of date

- **Status:** Open.
- **Location:** `readme/USAGE.md`, `readme/DESCRIPTION.md`.
- **Actual behavior:** `USAGE.md` gives the menus under Inventory → Operations (lines 53-55; they are under Inventory → Products, `stock.menu_stock_inventory_control`), describes the manual recompute buttons (line 80 and following) that are commented out in `views/res_config_settings_views.xml`, says the area is required only on the marked accounts (line 24; it is required on any line with a stockable product, `deltatech_valuation_area`) and lists the customer refund as "+ in" (line 49; the code counts it as an out with a minus sign). `DESCRIPTION.md` describes the "smart validation" `_is_valuation_area_required` (lines 12 and 24), which is commented out in `models/account_move_line.py`, and recommends the server-side calls `recompute_all_amount()` (lines 31-32), which do not exist (see SV-007). Neither file mentions the Odoo 20 setting *Keep move value on retroactive recompute*.
- **Expected behavior:** Both match `FISA_CONSULTANT.md` and the code.
- **Suggested fix:** Rebuild `USAGE.md` from the consultant sheet (`usage-din-fisa` agent) and correct `DESCRIPTION.md`.

## SV-006 — P2: New valuation rows use the environment currency instead of their explicit company

- **Status:** Open.
- **Location:** `models/product_valuation.py`, `currency_id` default (line 60), `ProductValuation.get_valuation()` (lines 72-102) and `ProductValuationHistory.get_valuation()` (lines 471-530); `models/account_move.py`, `_recompute_valuation_keys()` (lines 33-53).
- **Trigger:** From an environment whose current company is A, post or recompute stock-accounting entries for an allowed company B with another currency, where valuation rows do not yet exist.
- **Actual behavior:** Both row helpers accept an explicit `company_id` and write B into the new row but omit `currency_id` and do not switch company. The default sets `currency_id` from `env.company` (A). Recomputed amounts are B company-currency amounts displayed with the A currency.
- **Evidence (20.0):** Reproduced in an Odoo shell on a 20.0 database: `product.valuation.get_valuation(..., company_id=B)` with B in EUR, called from company A in USD, created a row with company B and currency USD.
- **Impact:** Valuation and history rows display amounts under the wrong currency and can pollute monetary reporting across companies.
- **Suggested fix:** Resolve the explicit company before creating rows and use its `currency_id`, or create under `with_company`; review existing mismatched rows for migration.
- **Validation needed:** Current/history row creation for a non-current allowed company, posting mixed-company moves, and labels/amounts before and after a full rebuild.

## SV-007 — P2: Stock valuation server action calls removed public methods

- **Status:** Open.
- **Location:** `data/data.xml`, `action_product_valuation_history_recompute` (lines 4-12).
- **Trigger:** Run the installed *Recompute All Stock Valuation* server action directly or through an automation that references it.
- **Actual behavior:** Its Python code calls `recompute_all_amount()` on both valuation models. The implementations expose only `_recompute_all_amount()`; the public names are not defined anywhere in the suite. The action fails on the first call.
- **Evidence (20.0):** Executed the installed action in an Odoo shell on a 20.0 database: `ValueError: AttributeError("'product.valuation.history' object has no attribute 'recompute_all_amount'")`.
- **Impact:** The installed server action cannot rebuild valuations and fails for callers using it.
- **Suggested fix:** Update the action to supported methods behind the appropriate administrative access checks, and align `readme/DESCRIPTION.md` (see SV-005).
- **Validation needed:** Execute the installed action as an authorized administrator and verify both history and current valuation recomputation; verify unauthorized execution is rejected.

## Review limitations

SV-001, SV-006 and SV-007 were reproduced in an Odoo shell on a 20.0 database (changes rolled
back). SV-002, SV-003, SV-004 and SV-005 were confirmed by reading the 20.0 source; no
multi-company or cron reproduction was run. No fixes have been applied.
