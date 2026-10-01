## 19.0.1.0.3 (2026-10-01)

- Fix: reversing a stock journal entry on a company without storno doubled the quantity
  instead of cancelling it. The core moves the amount to the opposite side but copies the
  quantity with the same sign; the quantity of the entry lines is signed (positive on
  debit, negative on credit), so it is now inverted together with the side. With storno
  the line stays on the same side (negative amount) and the quantity is unchanged.
- Fix: with storno, reversing a zero-value stock entry line (a move at cost 0) doubled the
  quantity: the line has no amount sign to cancel it, so its quantity is now inverted too.

## 19.0.1.0.2 (2026-10-01)

- Docs: consultant sheet updated to the current code (11-section structure), screenshots
  regenerated in Romanian on the Romanian chart of accounts; the screenshot test now posts
  real stock entries and checks them before taking the screenshots.
- Docs: known bugs listed in `readme/bugs.md`.

## 19.0.1.0.1 (2026-09-30)

- Own module icon in the flat style of the other modules.
