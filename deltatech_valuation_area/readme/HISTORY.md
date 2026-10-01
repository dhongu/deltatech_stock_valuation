## 20.0.1.0.5 (2026-10-01)

- Fix: reversing a stock journal entry on a company without storno doubled the quantity
  instead of cancelling it. The core moves the amount to the opposite side but copies the
  quantity with the same sign; the quantity of the entry lines is signed (positive on
  debit, negative on credit), so it is now inverted together with the side. With storno
  the line stays on the same side (negative amount) and the quantity is unchanged.

## 20.0.1.0.4 (2026-10-01)

- Fix (VA-001): the area of a stock move is taken from the warehouse of its internal location when
  the location has no area of its own; inventory adjustments and manual transfers no longer fall
  back to the company default area.
- Fix (VA-003): internal moves between locations of different areas are now refused when the move
  is validated, for the move and for each of its lines, with or without `deltatech_obyc`.
- Fix (VA-002): optional Product, Quantity and UoM columns on the journal items of manual entries;
  optional Quantity and Valuation Area columns on the journal items list.
- Fix (VA-004): Romanian wording unified on "arie de evaluare" (translations reloaded on upgrade);
  menu "Valuation Areas" visible only to accounting managers; area form in a sheet; stock journal
  limited to general journals of the area company; clearer help on the code; settings layout.
- Docs: description and consultant sheet updated; `readme/bugs.md` statuses.

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
