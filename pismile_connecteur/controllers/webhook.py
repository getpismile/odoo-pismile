# -*- coding: utf-8 -*-
import json
import logging

from odoo import SUPERUSER_ID, http
from odoo.http import request

from ..models.client import verifier_signature

_logger = logging.getLogger(__name__)


class PismileWebhook(http.Controller):
    """Réception des événements pismile : POST /pismile/webhook/<id de la société>, signé (Pismile-Signature)."""

    @http.route("/pismile/webhook/<int:company_id>", type="http", auth="public", methods=["POST"], csrf=False,
                save_session=False)
    def recevoir(self, company_id, **_kw):
        env = request.env(user=SUPERUSER_ID)
        company = env["res.company"].browse(company_id).exists()
        if not company or not company.pismile_secret_webhook:
            return request.make_response("inconnu", status=404)

        corps = request.httprequest.get_data()
        if not verifier_signature(company.pismile_secret_webhook, request.httprequest.headers.get("Pismile-Signature"),
                                  corps):
            _logger.warning("pismile : webhook refusé pour la société %s (signature invalide ou trop ancienne)",
                            company_id)
            return request.make_response("signature invalide", status=401)

        try:
            evenement = json.loads(corps.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return request.make_response("corps illisible", status=400)

        env["pismile.demande"].with_company(company)._pismile_traiter_evenement(evenement, company)
        _logger.info("pismile : événement %s (%s) traité pour la société %s", evenement.get("id"),
                     evenement.get("type"), company_id)
        return request.make_response("ok", status=200)
