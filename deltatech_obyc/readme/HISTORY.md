## 19.0.1.0.2 (2026-09-30)

- Own module icon in the flat style of the other modules.

## 19.0.1.0.1 (2026-08-19)

- Fix: dropship moves (supplier -> customer) for products with an OBYC valuation class were
  not valued — `stock.move.value` stayed 0, because the `stock_account` core fills this
  field only for `is_in` moves, not for `is_dropship` ones. The journal entry generated
  right after was posted with debit=0/credit=0 — apparently recorded, but with no value.
