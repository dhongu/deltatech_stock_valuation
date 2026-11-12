## 19.0.1.0.2 (2026-11-12)

- The moves of the transfer (and of the reversal transfer on cancel) are linked to the journal entry of the document, and a transfer between two internal locations gets the value of the line on its moves. Without this the stock reports (analytic stock balance, stock sheet) did not show the reclassification: they take the stock account and the value of a move from its entry, so the analytic balance stayed on the source account while the entry moved the value.
- "Cancel" of a validated document is now **Reverse** (state **Reversed**): the reversal entry has the same amounts with the accounts swapped, in positive amounts, instead of a negative "storno" entry, because the stock reports read the accounts of a reclassification from the debit and the credit of the entry. The reversal entry is posted with elevated rights, so the operator who validated the document can also reverse it without accounting rights. A draft document has no Cancel button any more: it is deleted, so the state Reversed always means a document that had a transfer and an entry.
- With `l10n_ro_stock_gestiune` installed, the entry of a document with one line is also set as the inter-warehouse transfer entry of its move, so that the stock sheet per warehouse or location shows the source account on the source and the destination account on the destination (it needs `l10n_ro_stock_gestiune` 19.0.3.1.8 or newer, which does not post its own transfer entry for these moves). The sheet pairs the entry with the move without looking at the product, so a document with several lines does not write it: its entry would be repeated for every move.
- The reverse transfer uses the operation type of the original transfer (it took the first internal type found, for example Quality Control, when the destination of the document was a location outside the warehouses), and its move gets the value of the document, so that the stock reports match the reversal entry even if the cost of the product changed meanwhile.
- The context key that stops the automatic valuation entry is renamed `skip_stock_valuation_entry` (it needs `deltatech_obyc` 19.0.1.0.23 or newer when both are installed).

## 19.0.1.0.1 (2026-11-11)

- Fix: a document with two lines of the same product could not be validated: the transfer merged their moves on confirmation and the lines no longer matched the moves. The moves are now confirmed without merge.
- The accounts of a rule must belong to the company of the rule.

## 19.0.1.0.0 (2026-11-11)

- First version: reclassification rules by pair of accounts, the reclassification document with products (lot/serial required for tracked products, vendor bill line optional), validation with transfer and journal entry, cancellation with reversal, dedicated groups.
