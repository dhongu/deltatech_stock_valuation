# Known bugs

Review date: 2026-10-01. Target version: Odoo 20.

## VA-001 — P2: The warehouse area is ignored on inventory adjustments and manual transfers

- **Status:** Fixed in 20.0.1.0.4 (port of the 19.0 fix). `stock.move._get_valuation_area()` takes
  the area of an internal location from the location itself, then from the warehouse of the
  location (`stock.location._get_valuation_area()`), before the procurement warehouse of the move
  and the company default. Tests: `test_va001_*` in `tests/test_valuation_area_bugs.py`.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (lines 20–21: `self.warehouse_id.valuation_area_id`).
- **Trigger:** Set an area on a warehouse only (not on its stock location), then validate an inventory adjustment or a manual transfer.
- **Actual behavior:** `stock.move.warehouse_id` is the procurement warehouse (`odoo/addons/stock/models/stock_move.py`, line 168); it is empty on inventory adjustments and on manually created moves, so the area of the warehouse is not used and the move falls back to the location area or the company default.
- **Expected behavior:** The area of the warehouse of the source/destination location is used.
- **Impact:** Stock entries are valued on the wrong area. In accounting terms, inventory gains and losses land on the wrong store, so offsetting them and charging the losses to the storekeeper are done on the wrong storekeeper. Before 20.0.1.0.4 the consultant sheet told to also set the area on the stock location, as a workaround.
- **Evidence:** Verified in an Odoo 20 shell on 2026-10-01 (database `test20_va`): area only on the warehouse, inventory adjustment on its stock location → `warehouse_id` empty, area = company default; same for a manual move from the supplier location.
- **Suggested fix:** Take the warehouse from `location_id.warehouse_id` / `location_dest_id.warehouse_id` when `warehouse_id` is empty.
- **Validation needed:** A test with the area set only on the warehouse, for an inventory adjustment and a manual transfer.

## VA-002 — P3: Area and quantity cannot be entered on manual journal entries

- **Status:** Fixed in 20.0.1.0.4. The journal items list of the entry form has the optional columns
  Product, Quantity and UoM (manual entries only) next to Valuation Area; `account.view_move_line_tree`
  has the optional columns Quantity and Valuation Area. Tests: `test_va002_*`.
- **Priority:** lowered from P2 to P3 on 2026-10-01: a missing UI field with an import workaround,
  not a wrong behaviour.
- **Location:** `views/account_move_view.xml` (lines 9–10).
- **Trigger:** Create a manual journal entry on a stock account.
- **Actual behavior:** The view only adds the area on the journal items; the journal items list of the entry form (`odoo/addons/account/views/account_move_views.xml`, page `aml_tab`, line 1518) has no `product_id`, `quantity` or `product_uom_id` columns, and `view_move_line_tree` (same file, line 160) has `product_id` but no `quantity` / `valuation_area_id`.
- **Expected behavior:** A manual stock entry (corrections, opening balances) can carry the product, the signed quantity and the area.
- **Impact:** Manual stock entries can only be made by import or integration.
- **Suggested fix:** Add the optional columns to the journal items list of the entry form and to the journal items list view.
- **Validation needed:** A UI test creating a manual entry with product, quantity and area.

## VA-003 — P2: Blocking internal transfers between areas never triggers without deltatech_obyc

- **Status:** Fixed in 20.0.1.0.4. The check moved from `_get_valuation_area()` to
  `stock.move._check_internal_move_valuation_area()`, called from `_action_done()`, so it runs on
  every validation, with or without `deltatech_obyc`. It compares the effective areas (location →
  warehouse of the location → company default) of the move and of each move line (putaway on a
  sub-location). Tests: `test_va003_*`.
- **Still open:** the transit route between areas (value of internal ↔ transit moves with
  `deltatech_obyc` and OBYC rules) is not verified; it belongs to `deltatech_obyc` (OBYC-009). The
  check above skips moves to or from a transit location (`usage != "internal"`), so the transit
  route is not blocked, but it is not a validated workaround either: the consultant sheet does not
  recommend it.
- **Location:** `models/stock_move.py`, `_get_valuation_area()` (lines 26–30), reached only from `_get_account_move_line_vals()` (line 47).
- **Trigger:** An internal transfer between two locations of different areas, without `deltatech_obyc`.
- **Actual behavior:** In Odoo 20 the internal transfer creates no journal entry (`odoo/addons/stock_account/models/stock_move.py`, `_should_create_account_move()`, lines 755–763: a location with a valuation account is required), so the check is never reached and the transfer is validated. With `deltatech_obyc` it is reached for products with an OBYC valuation class (`deltatech_obyc/models/stock_move.py`, `_create_account_move()` → `_get_obyc_stock_journal()` → `_get_valuation_area()`; deduced from the code, not verified on a database).
- **Expected behavior:** The rule is either applied on the stock move, or documented as working only with `deltatech_obyc`.
- **Impact:** The goods physically move to the destination store, but the value and the quantity per area stay on the source area, with no error.
- **Evidence:** Verified in an Odoo 20 shell on 2026-10-01 without `deltatech_obyc`: the internal picking was validated (`done`), without journal entry and without error.
- **Note on the transit route:** internal → transit and transit → internal moves use the `internal_transfer_out` / `internal_transfer_in` keys of `deltatech_obyc`, so they only create entries with OBYC rules for those keys. In Odoo 19 these moves are neither `is_in` nor `is_out`, so `_set_value()` is not called and `stock.move.value` / `_get_valued_qty()` may be 0 on them (deduced from the 19.0 code; `_set_value()` differs in 20.0, not verified on 20.0 — see OBYC-009).
- **Validation needed:** A test with and without `deltatech_obyc`, including the transit route with OBYC rules, checking the value and the quantity of the entries.

## VA-004 — P3: Interface issues

- **Status:** Fixed in 20.0.1.0.4:
  - `ro.po` uses "arie de evaluare" everywhere; the menu and the action are "Valuation Areas" /
    "Arii de evaluare"; a post-migration reloads the translations with overwrite, otherwise an
    upgrade keeps the old wording;
  - settings: label and field in a `row` with columns;
  - area form inside a `<sheet>`, in two columns;
  - `stock_journal_id` restricted to general journals of the area company (`check_company`,
    `_check_company_auto`);
  - help of `code`: the code is shown in front of the name;
  - the areas menu is visible only to `account.group_account_manager`, the group that can write
    areas (an accounting manager still needs the stock manager group to see the parent menu);
  - `DESCRIPTION.md` and the consultant sheet updated, screenshots regenerated.
  Tests: `test_va004_*`.
- **Terminology:** `i18n/ro.po` mixes "Zonă de evaluare" (menu line 78, settings checkbox lines 174/179, error messages lines 199/207) and "Arie de evaluare" (fields and list title, line 190); the source menu is "Evaluation Area" (`views/menu_views.xml`, line 8), the fields "Valuation Area".
- **Settings:** the label is glued to the value ("Arie de evaluare[STD]...") — `views/res_config_settings_views.xml`, line 16 (`label` + `oe_inline` field in a plain `div`).
- **Area form:** no `<sheet>`, the fields stretch over the whole screen width (`views/valuation_area_views.xml`, lines 19–26).
- **Area stock journal:** the field has no domain on the journal type or on the company (`models/valuation_area.py`, line 14).
- **Code field help:** says the code is used to determine the accounts (`models/valuation_area.py`, line 12); `deltatech_obyc` searches the account determination rules by area, not by code (`deltatech_obyc/models/product_account_determination.py`, `_get_rule_account()`).
- **Access:** the areas menu (under `stock.menu_warehouse_config`, `groups="stock.group_stock_manager"`) is visible to the stock manager, who has no write right on the areas (`security/ir.access.csv`, lines 2–3: `crud` only for `account.group_account_manager`); conversely, an accounting manager without the stock manager group can write the areas but does not see the menu.
- **DESCRIPTION.md:** still mentions `_prepare_account_move_line` (line 47) and the menu "Arii de Evaluare" (line 52).

## VA-005 — P3: The invoice line area is taken from the first linked stock move only

- **Status:** Open.
- **Location:** `models/account_move_line.py`, `_get_valuation_area()` (line 86: `stock_move = next(iter(stock_moves), None)`).
- **Trigger:** An invoice line whose purchase or sale line has stock moves in two areas (for example a purchase order received partly in two warehouses of different areas).
- **Actual behavior:** The whole invoice line gets the area of the first stock move.
- **Expected behavior:** The line is split per area in proportion to the quantities, or the mismatch is reported.
- **Impact:** The value of the invoice line is put on one area only; the stock account balance per area no longer matches the stock of the locations of each area.
- **Suggested fix:** Group the linked moves by area; when there is more than one, split the line or raise a warning for a manual correction.
- **Validation needed:** A test with a purchase line received in two areas, then invoiced.

## VA-006 — P3: The area is computed on every product line, not only on storable products

- **Status:** Open.
- **Location:** `models/account_move_line.py`, `_compute_valuation_area()` (line 101: the test is `line.product_id`, not `line.product_id.is_storable`).
- **Trigger:** A company using areas, with no default area, and an invoice line with a service or consumable product and no linked stock move.
- **Actual behavior:** The area is set on service and consumable lines too; with no default area, choosing any product on the line raises "Valuation area is not defined".
- **Expected behavior:** The area is computed (and required) only for storable products, as `_is_valuation_area_required()` already does.
- **Impact:** Invoices with services are blocked when the company has no default area; area tags on non-stock lines must be filtered out of reports.
- **Suggested fix:** Compute the area only when `line.product_id.is_storable`, or call `_get_valuation_area(raise_if_not_found=False)` for the other products.
- **Validation needed:** A test with a service line on a company with areas and no default area.

## VA-007 — P2: Reversing a stock journal entry counted the quantity twice

- **Status:** Fixed in 20.0.1.0.5. `account.move.line._copy_data_extend_business_fields()` (called by
  the core only on reversal, with `include_business_fields`) inverts the quantity of the product
  lines of `entry` moves when the company has no storno, and, with storno, on zero-value lines
  only. Tests: `tests/test_reversal_no_storno.py` in `deltatech_stock_valuation`.
- **Location:** `models/account_move_line.py`, `_copy_data_extend_business_fields()`.
- **Trigger:** **Reverse Entry** on a stock journal entry, (a) on a company without storno, or (b) with storno, on a line of value 0 (a move at cost 0).
- **Actual behavior:** `account.move._reverse_moves()` (`odoo/addons/account/models/account_move.py`, lines 5904–5912) copies the move and writes `balance = -balance` on the `entry` lines, plus `is_storno = not is_storno` when the company uses storno; the quantity is copied with the same sign. Without storno the reverse line moves to the opposite side but keeps the quantity sign, so the reversal of an entry counted one more entry (e.g. 10 units at 0 instead of 0). With storno the line stays on the same side with a negative amount, and the amount sign cancels the quantity, except on a zero-value line, which has no amount sign.
- **Expected behavior:** The reverse entry cancels both the value and the quantity per area.
- **Impact:** Wrong quantity (and average price) per area after a reversal. Entries reversed before 20.0.1.0.5 must be checked.
- **Evidence:** Reproduced by the tests of `deltatech_stock_valuation` 20.0.0.0.11.
