## 20.0.1.0.2 (2026-11-04)

- Migration to Odoo 20: depends on `pos_stock`, where the link between the POS and the
  stock pickings now lives; the hoot tests use `definePosStockModels` and the Python tests
  use `uom_id` on stock moves; Apps banner and page regenerated for Odoo 20.

## 19.0.1.0.2 (2026-11-04)

- Consultant sheet (`readme/FISA_CONSULTANT.md`), usage notes and screenshot.

## 19.0.1.0.1 (2026-10-23)

- Main image for the Odoo Apps Store (banner); the manifest points to it in `images`.

## 19.0.1.0.0 (2026-10-21)

- First version: a storable product without cost is stopped at the POS cart; the moves of
  POS orders are not checked again on the server.
