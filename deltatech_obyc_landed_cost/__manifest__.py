# ©  2026 Deltatech
# See README.rst file on addons root folder for license details


{
    "name": "OBYC - Landed Cost Class 6 Routing",
    "version": "19.0.1.0.1",
    "summary": "Landed costs on OBYC: route class 6 credit through an intermediary account",
    "category": "Valuation/Valuation",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "depends": [
        "deltatech_obyc",
        "stock_landed_costs",
        "purchase_stock",
        "account",
    ],
    "license": "OPL-1",
    "consultant_sheet": "full",
    "images": ["static/description/main_screenshot.png"],
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
