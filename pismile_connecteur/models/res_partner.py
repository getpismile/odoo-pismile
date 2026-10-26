# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    pismile_alias = fields.Char(
        "Alias PI-SPI",
        help="Alias PI-SPI du client (numéro de téléphone, SHID…) : la demande de paiement arrive dans sa banque "
             "ou son mobile money.")
