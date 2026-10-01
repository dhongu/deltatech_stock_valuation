# Known bugs

Review date: 2026-10-01. Target version: Odoo 19.

## VA-001 — P2: The warehouse area is ignored on inventory adjustments and manual transfers

- **Status:** Open.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (line 20: `self.warehouse_id.valuation_area_id`).
- **Trigger:** Set an area on a warehouse only (not on its stock location), then validate an inventory adjustment or a manual transfer.
- **Actual behavior:** `stock.move.warehouse_id` is the procurement warehouse; it is empty on inventory adjustments and manual transfers, so the area of the warehouse is not used and the move falls back to the location area or the company default.
- **Expected behavior:** The area of the warehouse of the source/destination location is used.
- **Impact:** Stock entries are valued on the wrong area. In accounting terms, inventory gains and losses land on the wrong store, so offsetting them and charging the losses to the storekeeper are done on the wrong storekeeper. The consultant sheet tells to also set the area on the stock location, as a workaround.
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
- **Impact:** The goods physically move to the destination store, but the value and the quantity per area stay on the source area, with no error.
- **Evidence:** Verified on 2026-10-01 without `deltatech_obyc`.
- **Note on the transit route:** internal → transit and transit → internal moves use the `internal_transfer_out` / `internal_transfer_in` keys of `deltatech_obyc`, so they only create entries with OBYC rules for those keys. In Odoo 19 these moves are neither `is_in` nor `is_out` (transit is a valued location), so `_set_value()` is not called and `stock.move.value` / `_get_valued_qty()` may be 0 on them (deduced from the code, not verified).
- **Validation needed:** A test with and without `deltatech_obyc`, including the transit route with OBYC rules, checking the value and the quantity of the entries.

## VA-004 — P3: Interface issues

- **Status:** Open.
- **Terminology:** `i18n/ro.po` mixes "Zonă de evaluare" (menu, settings checkbox, error messages) and "Arie de evaluare" (fields, list title); the source menu is "Evaluation Area", the fields "Valuation Area".
- **Settings:** the label is glued to the value ("Arie de evaluare[STD]...").
- **Area form:** no `<sheet>`, the fields stretch over the whole screen width.
- **Area stock journal:** the field has no domain on the journal type or on the company.
- **Code field help:** says the code is used to determine the accounts; `deltatech_obyc` searches by area, not by code.
- **Access:** the areas menu is visible to the stock manager, who has no write right on the areas.
- **DESCRIPTION.md:** still mentions `_prepare_account_move_line` and the menu "Arii de Evaluare".

## VA-005 — P3: The invoice line area is taken from the first linked stock move only

- **Status:** Open.
- **Location:** `models/account_move_line.py`, `_get_valuation_area()`: `stock_move = next(iter(stock_moves), None)`.
- **Trigger:** An invoice line whose purchase or sale line has stock moves in two areas (for example a purchase order received partly in two warehouses of different areas).
- **Actual behavior:** The whole invoice line gets the area of the first stock move.
- **Expected behavior:** The line is split per area in proportion to the quantities, or the mismatch is reported.
- **Impact:** The value of the invoice line is put on one area only; the stock account balance per area no longer matches the stock of the locations of each area.
- **Suggested fix:** Group the linked moves by area; when there is more than one, split the line or raise a warning for a manual correction.
- **Validation needed:** A test with a purchase line received in two areas, then invoiced.

## VA-006 — P3: The area is computed on every product line, not only on storable products

- **Status:** Open.
- **Location:** `models/account_move_line.py`, `_compute_valuation_area()`: the test is `line.product_id`, not `line.product_id.is_storable`.
- **Trigger:** A company using areas, with no default area, and an invoice line with a service or consumable product and no linked stock move.
- **Actual behavior:** The area is set on service and consumable lines too; with no default area, choosing any product on the line raises "Valuation area is not defined".
- **Expected behavior:** The area is computed (and required) only for storable products, as `_is_valuation_area_required()` already does.
- **Impact:** Invoices with services are blocked when the company has no default area; area tags on non-stock lines must be filtered out of reports.
- **Suggested fix:** Compute the area only when `line.product_id.is_storable`, or call `_get_valuation_area(raise_if_not_found=False)` for the other products.
- **Validation needed:** A test with a service line on a company with areas and no default area.
