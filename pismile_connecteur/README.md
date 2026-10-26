# PI-SPI Payment Requests (pismile) pour Odoo 18

Envoie les factures clients en demande de paiement PI-SPI (BCEAO). Le client valide dans sa banque ou son mobile
money ; l'argent arrive directement sur le compte de l'entreprise. La facture est marquée payée automatiquement.

## Prérequis

* Odoo 18 (Community ou Enterprise), module Comptabilité / Facturation.
* Un compte pismile avec le module Encaissement, un accès participant vérifié et un abonnement au connecteur Odoo.
* Une installation créée dans la console pismile (Encaissement → Connecteurs) : clé `pmc_live_…` ou `pmc_test_…`.

## Installation

1. Copier le dossier `pismile_connecteur` dans le dossier des modules (addons) d'Odoo.
2. Applications → Mettre à jour la liste des applications → installer « PI-SPI Payment Requests ».

## Configuration (Comptabilité → Configuration → Paramètres → bloc pismile)

1. **Clé pismile** : coller la clé de l'installation. Bouton **Tester la connexion**.
2. **Journal** : banque ou caisse où enregistrer les paiements reçus.
3. **Webhook** : copier l'adresse affichée (`https://votre-odoo/pismile/webhook/<société>`) dans la console pismile
   (installation → Événements), puis coller ici le secret `whsec_…` affiché par pismile.

Sans webhook, une tâche planifiée relit les événements toutes les 5 minutes : le webhook rend juste la mise à jour
immédiate.

Base multi-sociétés : chaque société a sa propre clé et sa propre adresse de webhook.
Serveur avec plusieurs bases : le webhook (auth publique) nécessite un `dbfilter` qui désigne la bonne base.

## Utilisation

1. Sur la fiche du client : renseigner son **Alias PI-SPI** (téléphone ou SHID), ou le saisir au premier envoi.
2. Sur une facture client validée en F CFA : bouton **Demander le paiement PI-SPI**.
3. Le statut apparaît dans la liste des factures (colonne PI-SPI) et dans l'onglet PI-SPI de la facture.
4. Payée : le paiement est créé dans le journal choisi et lettré avec la facture (mémo « PI-SPI <référence> »).
   Refusée ou expirée : un nouveau bouton permet de renvoyer la demande (référence « FAC/…-2 »).

Menu **Comptabilité → Clients → Demandes PI-SPI** : toutes les demandes, filtres par statut.

## Mode test

Avec une clé `pmc_test_…`, aucune vraie demande n'est envoyée : pismile simule le résultat après ~10 s
(montant se terminant par 13 → refusée, par 99 → expirée, sinon payée). L'option « Enregistrer les paiements de
test » crée alors le paiement simulé (à décocher sur une base réelle).
