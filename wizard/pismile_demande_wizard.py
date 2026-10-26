# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.client import ErreurPismile
from ..models.pismile_demande import STATUT_API, _datetime

ALIAS = re.compile(r"^[A-Za-z0-9+@._\-]{3,100}$")


class PismileDemandeWizard(models.TransientModel):
    _name = "pismile.demande.wizard"
    _description = "Demander le paiement PI-SPI"

    move_id = fields.Many2one("account.move", required=True, readonly=True)
    partner_id = fields.Many2one(related="move_id.partner_id")
    currency_id = fields.Many2one(related="move_id.currency_id")
    alias = fields.Char("Alias PI-SPI du client", required=True,
                        help="Numéro de téléphone ou SHID du client : il reçoit la demande dans sa banque.")
    enregistrer_alias = fields.Boolean("Enregistrer cet alias sur la fiche du client", default=True)
    montant = fields.Monetary("Montant", currency_field="currency_id", required=True)
    motif = fields.Char("Motif", help="Affiché dans la banque du client. Par défaut : « Facture <numéro> ».")

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        move = self.env["account.move"].browse(valeurs.get("move_id") or self.env.context.get("default_move_id"))
        if move:
            valeurs.setdefault("alias", move.partner_id.commercial_partner_id.pismile_alias
                               or move.partner_id.pismile_alias)
            valeurs.setdefault("montant", move.amount_residual)
        return valeurs

    def action_envoyer(self):
        self.ensure_one()
        move = self.move_id
        if not move.pismile_possible:
            raise UserError(_("Cette facture ne peut plus recevoir de demande PI-SPI."))
        alias = re.sub(r"\s", "", self.alias or "")
        if not ALIAS.match(alias):
            raise UserError(_("Alias PI-SPI invalide : numéro de téléphone ou SHID du client."))
        montant = int(round(self.montant))
        if montant <= 0 or montant > int(round(move.amount_residual)):
            raise UserError(_("Le montant doit être positif et ne pas dépasser le reste à payer."))

        reference = move._pismile_prochaine_reference()
        client = move.company_id._pismile_client()
        try:
            reponse = client.creer_demande(
                reference=reference, montant=montant, alias=alias,
                nom=move.partner_id.commercial_partner_id.name,
                motif=self.motif or None,
                echeance=move.invoice_date_due.isoformat() if move.invoice_date_due
                and move.invoice_date_due > fields.Date.context_today(self) else None,
                metadonnees={"odoo_move_id": str(move.id), "odoo_base": self.env.cr.dbname[:200]})
        except ErreurPismile as e:
            raise UserError(e.message)

        if self.enregistrer_alias:
            partenaire = move.partner_id.commercial_partner_id
            if partenaire.pismile_alias != alias:
                partenaire.pismile_alias = alias

        demande = self.env["pismile.demande"].create({
            "move_id": move.id,
            "reference": reponse.get("reference") or reference,
            "montant": reponse.get("montant", montant),
            "alias_masque": (reponse.get("payeur") or {}).get("alias"),
            "statut": STATUT_API.get(reponse.get("statut"), "en_attente"),
            "pismile_id": reponse.get("id"),
            "test": bool(reponse.get("test")),
            "echeance": _datetime(reponse.get("echeance")),
        })
        move.message_post(body=Markup("<b>PI-SPI</b> : demande %s envoyée à %s pour %s F CFA%s") % (
            demande.reference, demande.alias_masque or "", montant, " (test)" if demande.test else ""))
        return {"type": "ir.actions.act_window_close"}
