# -*- coding: utf-8 -*-
from odoo import fields, models

from .client import URL_PAR_DEFAUT, ClientPismile


class ResCompany(models.Model):
    """Réglages pismile par société : chaque société a sa propre installation (clé) chez pismile."""

    _inherit = "res.company"

    pismile_url_api = fields.Char("Adresse de l'API pismile", default=URL_PAR_DEFAUT)
    pismile_cle = fields.Char("Clé pismile", groups="base.group_system",
                              help="Clé de l'installation, créée dans la console pismile (pmc_live_… ou pmc_test_…).")
    pismile_secret_webhook = fields.Char("Secret du webhook", groups="base.group_system",
                                         help="Secret de signature whsec_… affiché par la console pismile.")
    pismile_journal_id = fields.Many2one(
        "account.journal", "Journal des encaissements PI-SPI",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', id)]",
        help="Journal où sont enregistrés les paiements reçus par PI-SPI.")
    pismile_paiement_test = fields.Boolean(
        "Enregistrer les paiements de test", default=True,
        help="Avec une clé de test, enregistrer quand même le paiement simulé (base de test seulement).")
    pismile_curseur = fields.Char("Curseur des événements pismile", default="0", copy=False)

    def _pismile_client(self):
        self.ensure_one()
        return ClientPismile(self.sudo().pismile_url_api, self.sudo().pismile_cle)
