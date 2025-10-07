# ©  2024 Deltatech
# See README.rst file on addons root folder for license details


{
    "name": "Deltatech Stock Valuation Area",
    "version": "19.0.1.0.0",
    "summary": "Stock Valuation Area Management",
    "category": "Valuation/Valuation",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "data": [
        "security/ir.model.access.csv",
        "views/valuation_area_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_location_views.xml",
        "views/warehouse_views.xml",
        "views/menu_views.xml",
        "views/account_move_view.xml",
    ],
    "depends": ["stock", "account", "stock_account"],
    "license": "LGPL-3",
    "images": ["static/description/main_screenshot.png"],
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
