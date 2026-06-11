# Changelog

## 18.0.0.0.6

* **[FIX]** Inverted UoM conversion when deriving stock quantity from accounting
  move lines. The aggregation used `quantity * uom_line.factor / uom_template.factor`,
  which multiplies instead of dividing by the line UoM factor (Odoo conversion to the
  reference UoM is `quantity / line.factor * template.factor`). The bug was dormant when
  move lines use the product's reference UoM (factor 1) but inflated quantities for
  products posted in a different UoM. Fixed in all five aggregation queries
  (`_get_sql_sub_select`, step 2 and step 4 of the history recompute). Validated on a
  real client dataset (valshop): total absolute quantity deviation vs `stock.quant`
  dropped by ~56%. Added regression test `test_uom_conversion_to_reference`
  (posts a line in a non-reference UoM and asserts the converted quantity).
