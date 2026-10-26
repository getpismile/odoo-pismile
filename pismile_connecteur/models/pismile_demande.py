# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timezone

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .client import ErreurPismile

_logger = logging.getLogger(__name__)

STATUTS = [
    ("en_attente", "En attente"),
    ("paye", "Payée"),
    ("refuse", "Refusée"),
    ("annule", "Annulée"),
    ("expire", "Expirée"),
    ("echec", "Échec d'envoi"),
]
STATUT_API = {
    "EN_ATTENTE": "en_attente", "PAYE": "paye", "REFUSE": "refuse",
    "ANNULE": "annule", "EXPIRE": "expire", "ECHEC": "echec",
}
FINALS = ("paye", "refuse", "annule", "expire", "echec")


class PismileDemande(models.Model):
    """Une demande de paiement PI-SPI envoyée pour une facture (une facture peut en avoir plusieurs essais)."""

    _name = "pismile.demande"
    _description = "Demande de paiement PI-SPI"
    _order = "create_date desc, id desc"
    _rec_name = "reference"

    move_id = fields.Many2one("account.move", "Facture", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="move_id.company_id", store=True, index=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True)
    currency_id = fields.Many2one(related="move_id.currency_id")
    reference = fields.Char("Référence", required=True, readonly=True, index=True)
    montant = fields.Monetary("Montant", currency_field="currency_id", readonly=True)
    alias_masque = fields.Char("Alias du client", readonly=True)
    statut = fields.Selection(STATUTS, "Statut", default="en_attente", required=True, readonly=True, index=True)
    pismile_id = fields.Char("Identifiant pismile", readonly=True, index=True, copy=False)
    reference_pispi = fields.Char("Référence PI-SPI", readonly=True, copy=False,
                                  help="Identifiant de bout en bout PI-SPI, pour le rapprochement bancaire.")
    raison = fields.Char("Raison", readonly=True)
    test = fields.Boolean("Test", readonly=True)
    echeance = fields.Datetime("Échéance", readonly=True)
    paye_le = fields.Datetime("Payée le", readonly=True)
    payment_id = fields.Many2one("account.payment", "Paiement", readonly=True, copy=False)

    _sql_constraints = [
        ("reference_societe_unique", "unique(reference, company_id)", "Cette référence pismile existe déjà."),
    ]

    # ------------------------------------------------------------------ événements

    @api.model
    def _pismile_traiter_evenement(self, evenement, company):
        """Applique un événement pismile (webhook ou curseur). Idempotent : le rejouer ne change rien."""
        type_ = evenement.get("type")
        if type_ == "test":
            _logger.info("pismile : événement de test reçu pour la société %s", company.id)
            return True
        donnees = evenement.get("donnees") or {}
        return self._pismile_appliquer(donnees, company)

    @api.model
    def _pismile_appliquer(self, donnees, company):
        """Met une demande à jour à partir de sa vue pismile ({id, reference, statut, …})."""
        demande = self.sudo().search([("pismile_id", "=", donnees.get("id")), ("company_id", "=", company.id)],
                                     limit=1) if donnees.get("id") else self.browse()
        if not demande and donnees.get("reference"):
            demande = self.sudo().search([("reference", "=", donnees["reference"]), ("company_id", "=", company.id)],
                                         limit=1)
        if not demande:
            _logger.info("pismile : demande %s inconnue dans cette base, ignorée", donnees.get("reference"))
            return False
        demande._pismile_mettre_a_jour(donnees)
        return True

    def _pismile_mettre_a_jour(self, donnees):
        self.ensure_one()
        nouveau = STATUT_API.get(donnees.get("statut"), "en_attente")
        valeurs = {}
        if self.statut not in FINALS and nouveau != self.statut:
            valeurs["statut"] = nouveau
        if donnees.get("referencePispi") and not self.reference_pispi:
            valeurs["reference_pispi"] = donnees["referencePispi"]
        if donnees.get("raison"):
            valeurs["raison"] = donnees["raison"][:250]
        if donnees.get("payeLe") and not self.paye_le:
            valeurs["paye_le"] = _datetime(donnees["payeLe"])
        if valeurs:
            self.write(valeurs)
            if "statut" in valeurs:
                self._pismile_annoncer()
        if self.statut == "paye":
            self._pismile_enregistrer_paiement()

    def _pismile_annoncer(self):
        libelle = dict(STATUTS).get(self.statut)
        corps = Markup("<b>PI-SPI</b> : demande %s — %s%s") % (
            self.reference, libelle, (" (%s)" % self.raison) if self.raison and self.statut != "paye" else "")
        self.move_id.message_post(body=corps)

    def _pismile_enregistrer_paiement(self):
        """Enregistre et lettre le paiement sur la facture, une seule fois."""
        self.ensure_one()
        if self.payment_id:
            return
        move = self.move_id.sudo()
        company = move.company_id
        if self.test and not company.pismile_paiement_test:
            return
        if move.state != "posted" or move.payment_state in ("paid", "in_payment", "reversed"):
            return
        journal = company.pismile_journal_id
        if not journal:
            move.message_post(body=_("PI-SPI : paiement reçu, mais aucun journal n'est choisi dans les paramètres "
                                     "pismile. Enregistrez le paiement à la main."))
            return
        montant = min(self.montant, move.amount_residual)
        if montant <= 0:
            return
        assistant = self.env["account.payment.register"].sudo().with_company(company).with_context(
            active_model="account.move", active_ids=move.ids).create({
                "journal_id": journal.id,
                "amount": montant,
                "payment_date": (self.paye_le or fields.Datetime.now()).date(),
                "communication": "PI-SPI %s %s" % (self.reference, self.reference_pispi or ""),
            })
        paiements = assistant._create_payments()
        self.sudo().payment_id = paiements[:1].id
        _logger.info("pismile : paiement %s enregistré pour %s", paiements[:1].name, move.name)

    # ------------------------------------------------------------------ tâche planifiée

    @api.model
    def _pismile_cron(self):
        """Toutes les 5 minutes : lit les événements par curseur (filet de sécurité des webhooks)."""
        societes = self.env["res.company"].sudo().search([("pismile_cle", "!=", False)])
        for company in societes:
            try:
                self._pismile_lire_evenements(company)
            except ErreurPismile as e:
                if e.code == "fonctionnalite_non_incluse":
                    self._pismile_relire_en_attente(company)
                else:
                    _logger.warning("pismile : événements de la société %s illisibles : %s", company.id, e.message)

    def _pismile_lire_evenements(self, company):
        client = company._pismile_client()
        curseur = company.pismile_curseur or "0"
        for _tour in range(20):  # 2000 événements au plus par passage
            page = client.evenements(curseur, 100)
            for evenement in page.get("evenements", []):
                self._pismile_traiter_evenement(evenement, company)
            curseur = page.get("suivant") or curseur
            company.pismile_curseur = curseur
            self.env.cr.commit()  # le curseur avance avec les écritures déjà faites
            if not page.get("plus"):
                break

    def _pismile_relire_en_attente(self, company):
        """Sans la fonctionnalité « événements » dans l'offre : relit une à une les demandes en attente."""
        client = company._pismile_client()
        for demande in self.sudo().search([("company_id", "=", company.id), ("statut", "=", "en_attente"),
                                           ("pismile_id", "!=", False)], limit=50):
            try:
                demande._pismile_mettre_a_jour(client.lire_demande(demande.pismile_id))
            except ErreurPismile as e:
                _logger.info("pismile : demande %s illisible : %s", demande.reference, e.message)

    def action_pismile_actualiser(self):
        """Bouton « Actualiser » : relit la demande chez pismile."""
        for demande in self.filtered("pismile_id"):
            try:
                demande._pismile_mettre_a_jour(demande.move_id.company_id._pismile_client().lire_demande(demande.pismile_id))
            except ErreurPismile as e:
                raise UserError(e.message)
        return True


def _datetime(valeur):
    """« 2026-10-25T02:46:17.894567473Z » → datetime naïf en UTC (format Odoo).

    Les fractions de seconde sont ramenées à 6 chiffres : Python 3.10 n'en accepte pas plus.
    """
    if not valeur:
        return False
    texte = valeur.strip().replace("Z", "+00:00")
    texte = re.sub(r"(\.\d{6})\d+", r"\1", texte)
    try:
        lu = datetime.fromisoformat(texte)
    except ValueError:
        return False
    if lu.tzinfo is not None:
        lu = lu.astimezone(timezone.utc).replace(tzinfo=None)
    return lu
