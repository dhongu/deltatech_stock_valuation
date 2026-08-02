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
