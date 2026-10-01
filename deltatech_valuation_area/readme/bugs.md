# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## VA-001 — P2: The warehouse area is ignored on inventory adjustments and manual transfers

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (line 20: `self.warehouse_id.valuation_area_id`).
- **Trigger:** Set an area on a warehouse only (not on its stock location), then validate an inventory adjustment or a manual transfer.
- **Actual behavior:** `stock.move.warehouse_id` is the procurement warehouse; it is empty on inventory adjustments and manual transfers, so the area of the warehouse is not used and the move falls back to the location area or the company default.
- **Expected behavior:** The area of the warehouse of the source/destination location is used.
- **Impact:** Stock entries are valued on the wrong area. The consultant sheet tells to also set the area on the stock location, as a workaround.
- **Evidence:** Verified in an Odoo shell on 2026-10-01.
- **Suggested fix:** Take the warehouse from `location_id.warehouse_id` / `location_dest_id.warehouse_id` when `warehouse_id` is empty.
- **Validation needed:** A test with the area set only on the warehouse, for an inventory adjustment and a manual transfer.

## VA-002 — P2: Area and quantity cannot be entered on manual journal entries

- **Status:** Open.
- **Location:** `views/account_move_view.xml`.
- **Trigger:** Create a manual journal entry on a stock account.
- **Actual behavior:** The view only adds the area on the journal items; the list has no `product_id`, `quantity` or `product_uom_id` columns, and `view_move_line_tree` has no `quantity` / `valuation_area_id`.
- **Expected behavior:** A manual stock entry (corrections, opening balances) can carry the product, the signed quantity and the area.
- **Impact:** Manual stock entries can only be made by import or integration.
- **Suggested fix:** Add the optional columns to the journal items list of the entry form and to the journal items list view.
- **Validation needed:** A UI test creating a manual entry with product, quantity and area.

## VA-003 — P2: Blocking internal transfers between areas never triggers without deltatech_obyc

- **Status:** Open.
- **Location:** the check on internal transfers between valuation areas.
- **Trigger:** An internal transfer between two locations of different areas, without `deltatech_obyc`.
- **Actual behavior:** The internal transfer creates no journal entry in Odoo 19, so the check is never reached. With `deltatech_obyc` it is likely reached for products with an OBYC valuation class (deduced from the code, not verified).
- **Expected behavior:** The rule is either applied on the stock move, or documented as working only with `deltatech_obyc`.
- **Evidence:** Verified on 2026-10-01 without `deltatech_obyc`.
- **Validation needed:** A test with and without `deltatech_obyc`.

## VA-004 — P3: Interface issues

- **Status:** Open.
- **Terminology:** `i18n/ro.po` mixes "Zonă de evaluare" (menu, settings checkbox, error messages) and "Arie de evaluare" (fields, list title); the source menu is "Evaluation Area", the fields "Valuation Area".
- **Settings:** the label is glued to the value ("Arie de evaluare[STD]...").
- **Area form:** no `<sheet>`, the fields stretch over the whole screen width.
- **Area stock journal:** the field has no domain on the journal type or on the company.
- **Code field help:** says the code is used to determine the accounts; `deltatech_obyc` searches by area, not by code.
- **Access:** the areas menu is visible to the stock manager, who has no write right on the areas.
- **DESCRIPTION.md:** still mentions `_prepare_account_move_line` and the menu "Arii de Evaluare".
