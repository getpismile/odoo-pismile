# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .client import ErreurPismile


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pismile_url_api = fields.Char(related="company_id.pismile_url_api", readonly=False)
    pismile_cle = fields.Char(related="company_id.pismile_cle", readonly=False, groups="base.group_system")
    pismile_secret_webhook = fields.Char(related="company_id.pismile_secret_webhook", readonly=False,
                                         groups="base.group_system")
    pismile_journal_id = fields.Many2one(related="company_id.pismile_journal_id", readonly=False)
    pismile_paiement_test = fields.Boolean(related="company_id.pismile_paiement_test", readonly=False)
    pismile_url_webhook = fields.Char("Adresse du webhook à copier dans pismile",
                                      compute="_compute_pismile_url_webhook")

    @api.depends("company_id")
    def _compute_pismile_url_webhook(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        for settings in self:
            settings.pismile_url_webhook = "%s/pismile/webhook/%s" % (base, settings.company_id.id)

    def action_pismile_tester(self):
        """« Tester la connexion » : appelle GET /moi avec la clé enregistrée."""
        self.ensure_one()
        self.execute()  # enregistre d'abord ce qui vient d'être saisi
        try:
            moi = self.company_id._pismile_client().moi()
        except ErreurPismile as e:
            raise UserError(e.message)
        installation = moi.get("installation") or {}
        offre = moi.get("offre") or {}
        message = _("Connecté à pismile : %(org)s · %(inst)s (%(mode)s) · offre %(offre)s.",
                    org=moi.get("organisation", "?"), inst=installation.get("nom", "?"),
                    mode=installation.get("mode", "?"), offre=offre.get("nom", "?"))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("pismile"), "message": message, "type": "success", "sticky": False},
        }
