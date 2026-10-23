# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

{
    "name": "Stock Valuation Guard",
    "version": "19.0.1.0.1",
    "images": ["static/description/main_screenshot.png"],
    "summary": "One cost method for every product category and no stock move without a value",
    "category": "Valuation/Valuation",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "depends": ["stock_account"],
    "data": [
        "data/ir_actions_server.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "license": "OPL-1",
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
