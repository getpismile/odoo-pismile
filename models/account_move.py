# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pismile_demande import STATUTS


class AccountMove(models.Model):
    _inherit = "account.move"

    pismile_demande_ids = fields.One2many("pismile.demande", "move_id", "Demandes PI-SPI", readonly=True)
    pismile_statut = fields.Selection(STATUTS, "PI-SPI", compute="_compute_pismile_statut", store=True,
                                      help="Statut de la dernière demande de paiement PI-SPI.")
    pismile_possible = fields.Boolean(compute="_compute_pismile_possible")

    @api.depends("pismile_demande_ids.statut")
    def _compute_pismile_statut(self):
        for move in self:
            derniere = move.pismile_demande_ids.sorted(lambda d: (d.create_date or fields.Datetime.now(), d.id))[-1:]
            move.pismile_statut = derniere.statut if derniere else False

    @api.depends("state", "move_type", "payment_state", "currency_id", "amount_residual", "pismile_statut")
    def _compute_pismile_possible(self):
        for move in self:
            move.pismile_possible = (
                move.state == "posted"
                and move.move_type == "out_invoice"
                and move.payment_state not in ("paid", "in_payment", "reversed")
                and move.currency_id.name == "XOF"
                and move.amount_residual > 0
                and move.pismile_statut != "en_attente"
            )

    def action_pismile_demander(self):
        """Ouvre l'assistant : alias du client et montant, puis envoi."""
        self.ensure_one()
        if not self.pismile_possible:
            raise UserError(_("Une demande PI-SPI se fait sur une facture client validée, en F CFA, non payée, "
                              "sans autre demande en attente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Demander le paiement PI-SPI"),
            "res_model": "pismile.demande.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _pismile_prochaine_reference(self):
        """« FAC/2026/00012 », puis « FAC/2026/00012-2 » pour un nouvel essai après un refus ou une expiration."""
        self.ensure_one()
        base = (self.name or "FACT-%s" % self.id).replace(" ", "-")[:58]
        essais = len(self.pismile_demande_ids)
        return base if essais == 0 else "%s-%s" % (base, essais + 1)
