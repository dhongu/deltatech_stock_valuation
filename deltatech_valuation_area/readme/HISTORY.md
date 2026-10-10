## 19.0.1.0.5 (2026-10-06)

- In the valuation area dropdown the code is shown in a second, dimmed column; the areas can
  also be searched by code. The plain name, `[CODE] Name`, is unchanged.

## 19.0.1.0.4 (2026-10-01)

- Fix: the area of a stock move is taken from the warehouse of its internal location when
  the location has no area of its own; inventory adjustments and manual transfers no longer fall
  back to the company default area.
- Fix: internal moves between locations of different areas are now refused when the move
  is validated, for the move and for each of its lines, with or without `deltatech_obyc`.
- Fix: optional Product, Quantity and UoM columns on the journal items of manual entries;
  optional Quantity and Valuation Area columns on the journal items list.
- Fix: Romanian wording unified on "arie de evaluare" (translations reloaded on upgrade);
  menu "Valuation Areas" visible only to accounting managers; area form in a sheet; stock journal
  limited to general journals of the area company; clearer help on the code; settings layout.
- Docs: description and consultant sheet updated.

## 19.0.1.0.3 (2026-10-01)

- Fix: reversing a stock journal entry on a company without storno doubled the quantity
  instead of cancelling it. The core moves the amount to the opposite side but copies the
  quantity with the same sign; the quantity of the entry lines is signed (positive on
  debit, negative on credit), so it is now inverted together with the side. With storno
  the line stays on the same side (negative amount) and the quantity is unchanged.
- Fix: with storno, reversing a zero-value stock entry line (a move at cost 0) doubled the
  quantity: the line has no amount sign to cancel it, so its quantity is now inverted too.
- Docs: consultant sheet revised after the accounting audit: legal basis, receipt / delivery /
  invoice gaps, inventory difference accounts per stock class, shortages (VAT and profit tax),
  reconciliation per area, transfers between areas and the sign convention on reversals; D300 from tax tags for the month-end entries.

## 19.0.1.0.2 (2026-10-01)

- Docs: consultant sheet updated to the current code (11-section structure), screenshots
  regenerated in Romanian on the Romanian chart of accounts; the screenshot test now posts
  real stock entries and checks them before taking the screenshots.

## 19.0.1.0.1 (2026-09-30)

- Own module icon in the flat style of the other modules.
