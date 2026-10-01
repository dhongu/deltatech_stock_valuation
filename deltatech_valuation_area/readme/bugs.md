# Known bugs

Review date: 2026-10-01. Target version: Odoo 20.

## VA-001 — P2: The warehouse area is ignored on inventory adjustments and manual transfers

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (lines 20–21: `self.warehouse_id.valuation_area_id`).
- **Trigger:** Set an area on a warehouse only (not on its stock location), then validate an inventory adjustment or a manual transfer.
- **Actual behavior:** `stock.move.warehouse_id` is the procurement warehouse (`odoo/addons/stock/models/stock_move.py`, line 168); it is empty on inventory adjustments and on manually created moves, so the area of the warehouse is not used and the move falls back to the location area or the company default.
- **Expected behavior:** The area of the warehouse of the source/destination location is used.
- **Impact:** Stock entries are valued on the wrong area. The consultant sheet tells to also set the area on the stock location, as a workaround.
- **Evidence:** Verified in an Odoo 20 shell on 2026-10-01 (database `test20_va`): area only on the warehouse, inventory adjustment on its stock location → `warehouse_id` empty, area = company default; same for a manual move from the supplier location.
- **Suggested fix:** Take the warehouse from `location_id.warehouse_id` / `location_dest_id.warehouse_id` when `warehouse_id` is empty.
- **Validation needed:** A test with the area set only on the warehouse, for an inventory adjustment and a manual transfer.

## VA-002 — P2: Area and quantity cannot be entered on manual journal entries

- **Status:** Open.
- **Location:** `views/account_move_view.xml` (lines 9–10).
- **Trigger:** Create a manual journal entry on a stock account.
- **Actual behavior:** The view only adds the area on the journal items; the journal items list of the entry form (`odoo/addons/account/views/account_move_views.xml`, page `aml_tab`, line 1518) has no `product_id`, `quantity` or `product_uom_id` columns, and `view_move_line_tree` (same file, line 160) has `product_id` but no `quantity` / `valuation_area_id`.
- **Expected behavior:** A manual stock entry (corrections, opening balances) can carry the product, the signed quantity and the area.
- **Impact:** Manual stock entries can only be made by import or integration.
- **Suggested fix:** Add the optional columns to the journal items list of the entry form and to the journal items list view.
- **Validation needed:** A UI test creating a manual entry with product, quantity and area.

## VA-003 — P2: Blocking internal transfers between areas never triggers without deltatech_obyc

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (lines 26–30), reached only from `_get_account_move_line_vals()` (line 47).
- **Trigger:** An internal transfer between two locations of different areas, without `deltatech_obyc`.
- **Actual behavior:** In Odoo 20 the internal transfer creates no journal entry (`odoo/addons/stock_account/models/stock_move.py`, `_should_create_account_move()`, lines 755–763: a location with a valuation account is required), so the check is never reached and the transfer is validated. With `deltatech_obyc` it is reached for products with an OBYC valuation class (`deltatech_obyc/models/stock_move.py`, `_create_account_move()` → `_get_obyc_stock_journal()` → `_get_valuation_area()`; deduced from the code, not verified on a database).
- **Expected behavior:** The rule is either applied on the stock move, or documented as working only with `deltatech_obyc`.
- **Evidence:** Verified in an Odoo 20 shell on 2026-10-01 without `deltatech_obyc`: the internal picking was validated (`done`), without journal entry and without error.
- **Validation needed:** A test with and without `deltatech_obyc`.

## VA-004 — P3: Interface issues

- **Status:** Open.
- **Terminology:** `i18n/ro.po` mixes "Zonă de evaluare" (menu line 78, settings checkbox lines 174/179, error messages lines 199/207) and "Arie de evaluare" (fields and list title, line 190); the source menu is "Evaluation Area" (`views/menu_views.xml`, line 8), the fields "Valuation Area".
- **Settings:** the label is glued to the value ("Arie de evaluare[STD]...") — `views/res_config_settings_views.xml`, line 16 (`label` + `oe_inline` field in a plain `div`).
- **Area form:** no `<sheet>`, the fields stretch over the whole screen width (`views/valuation_area_views.xml`, lines 19–26).
- **Area stock journal:** the field has no domain on the journal type or on the company (`models/valuation_area.py`, line 14).
- **Code field help:** says the code is used to determine the accounts (`models/valuation_area.py`, line 12); `deltatech_obyc` searches the account determination rules by area, not by code (`deltatech_obyc/models/product_account_determination.py`, `_get_rule_account()`).
- **Access:** the areas menu (under `stock.menu_warehouse_config`, `groups="stock.group_stock_manager"`) is visible to the stock manager, who has no write right on the areas (`security/ir.access.csv`, lines 2–3: `crud` only for `account.group_account_manager`); conversely, an accounting manager without the stock manager group can write the areas but does not see the menu.
- **DESCRIPTION.md:** still mentions `_prepare_account_move_line` (line 47) and the menu "Arii de Evaluare" (line 52).
