## 20.0.1.0.3 (2026-10-01)

- Fix: validating a landed cost on a product with an OBYC valuation class crashed with
  `AttributeError: 'int' object has no attribute 'id'`. `_get_product_accounts` returned
  account ids instead of `account.account` records, which the core (fiscal position
  `map_account`, landed cost entries) expects.
- Fix: a customer invoice for a product with an OBYC valuation class in real-time valuation
  could not be posted ("Transaction key is not defined"). The core builds the COGS lines
  of the invoice without a transaction key. With OBYC the cost of goods sold is already
  booked at delivery (`stock_delivery` key), so the invoice now gets no COGS lines for
  these products; other products keep the standard behavior.

## 20.0.1.0.2 (2026-10-01)

- Migration to Odoo 20: in 20 `stock.move.value` is negative on outgoing moves; the OBYC
  journal entry keeps posting the absolute value, so the Dr/Cr amounts are the same as in 19.
- Odoo 20 replays the valuation and rewrites the value of outgoing moves already done when an
  incoming move is backdated, a done quantity is edited or a vendor bill revalues a receipt.
  For products with an OBYC valuation class the move value stays the one posted at validation
  (as in 19), consistent with the OBYC journal entry; other products keep the Odoo 20 behaviour.
  This applies only while the company setting *Keep move value on retroactive recompute*
  (`deltatech_valuation_area`) is enabled (the default); when disabled, OBYC products also
  follow the standard Odoo 20 recompute.

## 19.0.1.0.2 (2026-09-30)

- Own module icon in the flat style of the other modules.

## 19.0.1.0.1 (2026-08-19)

- Fix: dropship moves (supplier -> customer) for products with an OBYC valuation class were
  not valued — `stock.move.value` stayed 0, because the `stock_account` core fills this
  field only for `is_in` moves, not for `is_dropship` ones. The journal entry generated
  right after was posted with debit=0/credit=0 — apparently recorded, but with no value.
