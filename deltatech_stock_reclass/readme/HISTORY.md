## 19.0.1.0.1 (2026-11-11)

- Fix: a document with two lines of the same product could not be validated: the transfer merged their moves on confirmation and the lines no longer matched the moves. The moves are now confirmed without merge.
- The accounts of a rule must belong to the company of the rule.

## 19.0.1.0.0 (2026-11-11)

- First version: reclassification rules by pair of accounts, the reclassification document with products (lot/serial required for tracked products, vendor bill line optional), validation with transfer and journal entry, cancellation with reversal, dedicated groups.
