# -*- coding: utf-8 -*-
{
    # Nom de la boutique Odoo Apps : 25 caractères au plus, sans nom de société (règles des vendeurs Odoo).
    "name": "PI-SPI Payment Requests",
    "summary": "Send customer invoices as PI-SPI (BCEAO) payment requests; payments are recorded and "
               "reconciled automatically. Requires a pismile account.",
    "description": """
PI-SPI payment requests for Odoo invoices (UEMOA, XOF).

The customer approves the request in their bank or mobile money app; the money goes straight to the
company's own account. The payment is then recorded and reconciled automatically.

Requires a pismile account (https://pismile.com) with the Collections module and a connector subscription.
Data sent to pismile when a user clicks "Request PI-SPI payment": invoice reference, amount, customer
PI-SPI alias and name, due date, and internal Odoo identifiers.
    """,
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "pismile",
    "maintainer": "pismile",
    "website": "https://pismile.com",
    "support": "support@pismile.com",
    "license": "LGPL-3",
    "images": ["static/description/banner.png"],
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/pismile_demande_views.xml",
        "views/account_move_views.xml",
        "wizard/pismile_demande_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
