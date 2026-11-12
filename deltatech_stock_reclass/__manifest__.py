# ©  2026 Terrabit
# See README.rst file on addons root folder for license details

{
    "name": "Stock Reclassification",
    "version": "19.0.1.0.2",
    "images": ["static/description/main_screenshot.png"],
    "summary": "Move stock from one account to another with a document, a transfer and a journal entry",
    "category": "Valuation/Valuation",
    "author": "Terrabit, Dorin Hongu",
    "website": "https://www.terrabit.ro",
    "depends": ["stock_account"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/reclassification_rule_views.xml",
        "views/reclassification_views.xml",
        "views/menu_views.xml",
    ],
    "license": "OPL-1",
    "consultant_sheet": "full",
    "development_status": "Beta",
    "maintainers": ["dhongu"],
}
