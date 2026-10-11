# ©  2008-2026 Deltatech
# See README.rst file on addons root folder for license details

{
    "name": "Lot valuation",
    "summary": "Stock valuation on each lot / serial number",
    "version": "19.0.1.0.0",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "category": "Inventory/Inventory",
    "depends": ["stock_account", "deltatech_stock_inventory"],
    "excludes": ["l10n_ro_stock_account"],
    "license": "OPL-1",
    "data": [
        "views/stock_lot_views.xml",
        "views/stock_quant_views.xml",
    ],
    "images": ["static/description/main_screenshot.png"],
    "maintainers": ["dhongu"],
    "development_status": "Beta",
}
