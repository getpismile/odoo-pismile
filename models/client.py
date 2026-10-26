# -*- coding: utf-8 -*-
"""Client de l'API pismile des connecteurs (v1). Aucune dépendance à l'ORM : facile à tester et à réutiliser."""
import hashlib
import hmac
import logging
import time

import requests

_logger = logging.getLogger(__name__)

URL_PAR_DEFAUT = "https://pismile.com/api/connect/v1"
DELAI = 15  # secondes
TOLERANCE_SIGNATURE = 300  # secondes : au-delà, un webhook est refusé (rejeu)


class ErreurPismile(Exception):
    """Refus de l'API pismile : code stable (ex. « quota_atteint ») et message court en français."""

    def __init__(self, code, message, statut=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.statut = statut


class ClientPismile:

    def __init__(self, url_api, cle):
        if not cle:
            raise ErreurPismile("configuration", "Renseignez la clé pismile dans Comptabilité → Configuration → Paramètres.")
        self.url_api = (url_api or URL_PAR_DEFAUT).rstrip("/")
        self.cle = cle.strip()

    # ------------------------------------------------------------------ API

    def moi(self):
        return self._appeler("GET", "/moi")

    def creer_demande(self, reference, montant, alias, nom=None, motif=None, echeance=None, metadonnees=None):
        corps = {"reference": reference, "montant": int(montant), "payeurAlias": alias}
        if nom:
            corps["payeurNom"] = nom[:150]
        if motif:
            corps["motif"] = motif[:100]
        if echeance:
            corps["echeance"] = echeance
        if metadonnees:
            corps["metadonnees"] = metadonnees
        return self._appeler("POST", "/demandes", corps)

    def lire_demande(self, demande_id):
        return self._appeler("GET", "/demandes/%s" % demande_id)

    def evenements(self, apres="0", limite=100):
        return self._appeler("GET", "/evenements", params={"apres": apres or "0", "limite": limite})

    # ------------------------------------------------------------------

    def _appeler(self, methode, chemin, corps=None, params=None):
        try:
            reponse = requests.request(
                methode, self.url_api + chemin, json=corps, params=params, timeout=DELAI,
                headers={"Authorization": "Bearer " + self.cle, "Accept": "application/json",
                         "User-Agent": "pismile-odoo/18.0"})
        except requests.RequestException as e:
            _logger.warning("pismile : %s %s injoignable (%s)", methode, chemin, type(e).__name__)
            raise ErreurPismile("injoignable", "pismile est injoignable pour le moment. Réessayez dans quelques minutes.")
        try:
            donnees = reponse.json() if reponse.content else {}
        except ValueError:
            donnees = {}
        if reponse.status_code >= 400:
            raise ErreurPismile(donnees.get("erreur", "http_%s" % reponse.status_code),
                                donnees.get("message") or "Réponse inattendue de pismile (HTTP %s)." % reponse.status_code,
                                reponse.status_code)
        return donnees


def verifier_signature(secret, entete, corps_brut, maintenant=None):
    """Vérifie « Pismile-Signature: t=<horodatage>,v1=<hex> » où v1 = HMAC-SHA256(secret, t + "." + corps).

    :param corps_brut: corps reçu, en octets, tel quel (avant tout décodage JSON)
    :return: True si la signature est valide et récente
    """
    if not secret or not entete:
        return False
    parties = {}
    for morceau in entete.split(","):
        if "=" in morceau:
            cle, valeur = morceau.split("=", 1)
            parties[cle.strip()] = valeur.strip()
    try:
        horodatage = int(parties.get("t", ""))
    except ValueError:
        return False
    if abs((maintenant or time.time()) - horodatage) > TOLERANCE_SIGNATURE:
        return False
    attendu = hmac.new(secret.encode("utf-8"), str(horodatage).encode("utf-8") + b"." + corps_brut,
                       hashlib.sha256).hexdigest()
    return hmac.compare_digest(attendu, parties.get("v1", ""))
