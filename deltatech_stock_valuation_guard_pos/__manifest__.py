# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

{
    "name": "Stock Valuation Guard - Point of Sale",
    "version": "19.0.1.0.0",
    "summary": "Stop products without cost at the POS cart, before the receipt is printed",
    "category": "Valuation/Valuation",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "depends": ["deltatech_stock_valuation_guard", "point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "deltatech_stock_valuation_guard_pos/static/src/js/pos_store.esm.js",
        ],
        "web.assets_unit_tests": ["deltatech_stock_valuation_guard_pos/static/tests/unit/**/*"],
    },
    "auto_install": True,
    "license": "OPL-1",
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
