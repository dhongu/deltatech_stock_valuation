## 19.0.0.0.12 (2026-10-02)

- The Usage screenshots on the Apps page are narrower (1245 px at most), so they no longer fill the whole page.

## 19.0.0.0.11 (2026-10-01)

- Fix: the recompute at posting counts the stock lines without a unit of measure (product unit),
  like the full recompute (SV-001).
- Fix: saving the settings and the full recompute move to the company area only the journal items of
  the current company, including the ones with no area (SV-002).
- Fix: the background recompute runs on the company it was started from, for the whole cycle; a
  manual step-by-step cycle cannot be continued from another company (SV-003).
- Fix: steps 2, 3, 4 and 6 of the full recompute no longer read or change the history of other
  companies (SV-009).
- Fix: the upgrade repairs the data written by the old version on multi-company databases: stock
  journal items moved to the area of another company go back to their company area, and valuation
  / history rows on the area of another company are removed; step 1 of the full recompute clears
  the whole history of the company. After the upgrade, reset a background run in progress and run
  Recompute All from each company.
- Fix: the valuation table on the product is read-only; internal users only read the valuation,
  write access goes to the accounting manager; posting still updates it (SV-004).
- Fix: new valuation rows take the currency of their company; the migration corrects existing
  rows (SV-006).
- Fix: the Recompute All Stock Valuation server action calls the current methods and is restricted
  to the system administrator (SV-007).
- Docs: `USAGE.md` rebuilt from the consultant sheet, `CONFIGURE.md` added, `DESCRIPTION.md` and the
  consultant sheet updated; product tab screenshot regenerated (SV-005).

## 19.0.0.0.10 (2026-10-01)

- Test: reversing a stock journal entry on a company without storno leaves the stock
  valuation at zero (the fix is in `deltatech_valuation_area` 19.0.1.0.3).
- Test: with storno, reversing a stock entry leaves the valuation at zero, including a
  zero-value line (move at cost 0).
- Docs: consultant sheet corrected after the accounting audit: OBYC recommended for Romanian
  clients and a month-end procedure for receipts and deliveries not invoiced without OBYC;
  a value-only adjustment changes the value and the average price; reversal with and without
  storno; month-end and stock count reconciliation; legal basis (OMFP 1802/2014, Fiscal Code);
  firm warning for multi-company databases. `readme/bugs.md`: SV-005 updated, SV-008 added.
- Docs: the screenshot test puts a supplier on the receipt entry; screenshots regenerated.

## 19.0.0.0.9 (2026-10-01)

- Docs: consultant sheet updated to the current code (11-section structure), screenshots
  regenerated in Romanian on the Romanian chart of accounts; the screenshot test now posts
  real stock entries and checks them before taking the screenshots.
- Docs: known bugs listed in `readme/bugs.md` (SV-001..007).

## 19.0.0.0.8 (2026-09-30)

- Own module icon in the flat style of the other modules.

### 19.0.0.0.7

* **[FIX]** Re-inverted the UoM conversion introduced in 19.0.0.0.6. That change was a
  mechanical backport of a fix validated on 18.0, but `uom.uom.factor` changed meaning in
  Odoo 19: it is now the ABSOLUTE quantity in the root unit (`Dozens` = 12, `kg` = 1000,
  `Minutes` = 0.0167), computed as `relative_factor * relative_uom_id.factor`. In 18.0 it
  was the inverse ratio, so the same formula means opposite things in the two versions.
  Correct conversion on 19.0 is `quantity * uom_line.factor / uom_template.factor`, which
  is what the five aggregation queries now use. On 18.0 the 19.0.0.0.6 formula stays
  correct — do not port this commit back.
* **[FIX]** `test_uom_conversion_to_reference` built its unit with the 18.0 API
  (`category_id`, `uom_type`), which no longer exists on `uom.uom` in Odoo 19 — the test
  died with `AttributeError` and never actually guarded the conversion. Rewritten with
  `relative_uom_id` + `relative_factor`. Verified to fail (`32.0 != 2.0`) against the
  19.0.0.0.6 formula and pass against this one.
* **[IMP]** Applied pending `ruff format` reformatting in the screenshot tests of
  `deltatech_obyc`, `deltatech_stock_valuation` and `deltatech_valuation_area`, which was
  keeping the repository's `pre-commit` job red.

### 19.0.0.0.6

* **[FIX]** Inverted UoM conversion when deriving stock quantity from accounting
  move lines. The aggregation used `quantity * uom_line.factor / uom_template.factor`,
  which multiplies instead of dividing by the line UoM factor (Odoo conversion to the
  reference UoM is `quantity / line.factor * template.factor`). The bug was dormant when
  move lines use the product's reference UoM (factor 1) but inflated quantities for
  products posted in a different UoM. Fixed in all five aggregation queries
  (`_get_sql_sub_select`, step 2 and step 4 of the history recompute). Backported from
  the 18.0 fix, which was validated on a real client dataset (total absolute quantity
  deviation vs `stock.quant` dropped ~56%). Added regression test
  `test_uom_conversion_to_reference`.
