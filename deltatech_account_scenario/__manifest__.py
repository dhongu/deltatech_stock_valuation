# ©  2024 Deltatech
# See README.rst file on addons root folder for license details
{
    "name": "Deltatech Account Scenario - Accounting Scenario Framework",
    "version": "19.0.1.0.0",
    "summary": "Framework for running and validating accounting scenarios via JSON",
    "category": "Accounting/Accounting",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "data": [
        "security/ir.model.access.csv",
        "wizards/stock_test_scenario_import_views.xml",
        "views/stock_test_scenario_views.xml",
        "views/stock_test_run_views.xml",
        "views/menu_views.xml",
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
            "deltatech_account_scenario/static/src/js/code_editor_patch.esm.js",
        ],
    },
    "demo": ["demo/load_demo_scenarios.xml"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
