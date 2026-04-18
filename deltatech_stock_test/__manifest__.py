# ©  2024 Deltatech
# See README.rst file on addons root folder for license details
{
    "name": "Deltatech Stock Test - Management Accounting Test Framework",
    "version": "19.0.1.0.0",
    "summary": "Framework for testing stock management accounting via JSON scenarios",
    "category": "Accounting/Accounting",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "data": [
        "security/ir.model.access.csv",
        "views/stock_test_scenario_views.xml",
        "views/stock_test_run_views.xml",
        "views/menu_views.xml",
        "data/load_demo_scenarios.xml",
    ],
    "depends": [
        "account",
        "stock",
        "stock_account",
        "purchase_stock",
        "sale_stock",
    ],
    "assets": {
        "web.assets_backend": [
            "deltatech_stock_test/static/src/js/code_editor_patch.esm.js",
        ],
    },
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
