## 20.0.1.0.3 (2026-10-01)

- Docs: consultant sheet updated for Odoo 20 (11-section structure): the *Keep move value on
  retroactive recompute* setting, the COGS lines of the customer invoice, the Odoo 20
  menus and labels; screenshots regenerated (new 09 for the customer invoice).
- Docs: known bugs listed in `readme/bugs.md`, checked against the Odoo 20 code.

## 20.0.1.0.2 (2026-10-01)

- New company setting *Keep move value on retroactive recompute* (Inventory → Settings →
  Valuation), enabled by default: validated stock moves keep the value computed at
  validation, as in Odoo 19. Disable it to use the standard Odoo 20 retroactive recompute
  (posted journal entries are not corrected).

## 20.0.1.0.1 (2026-09-30)

- Own module icon in the flat style of the other modules.
