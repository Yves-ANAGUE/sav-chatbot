"""
Service d'import du catalogue.

Responsabilité unique : orchestrer le téléchargement, le parsing,
la validation et l'insertion en base en utilisant bulk_create.

Complexité : O(n/batch_size) requêtes SQL au lieu de O(n).
"""
import logging
from dataclasses import dataclass, field
from typing import Generator
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CategorieProduit, HistoriqueImport, Produit
from .parseurs import parser_fakestore_api, parser_csv_generique
from .serializers import ProduitImportForm

logger = logging.getLogger(__name__)

URL_FAKESTORE = "https://fakestoreapi.com/products"
TAILLE_LOT_DEFAUT = 500


@dataclass
class ResultatImport:
    """VO immuable résumant le résultat d'un import."""
    nb_traites: int = 0
    nb_crees: int = 0
    nb_mis_a_jour: int = 0
    nb_erreurs: int = 0
    erreurs: list[str] = field(default_factory=list)

    @property
    def taux_succes(self) -> float:
        if self.nb_traites == 0:
            return 0.0
        return round((self.nb_traites - self.nb_erreurs) / self.nb_traites * 100, 1)


def _telecharger_json(url: str) -> list | dict:
    """Télécharge et désérialise du JSON depuis une URL publique."""
    requete = Request(url, headers={"User-Agent": "SAV-Chatbot/1.0"})
    try:
        with urlopen(requete, timeout=30) as reponse:
            contenu = reponse.read().decode("utf-8")
            return json.loads(contenu)
    except URLError as exc:
        raise ConnectionError(f"Impossible de télécharger {url} : {exc}") from exc


def _valider_et_grouper_par_lot(
    produits_bruts: Generator,
    taille_lot: int,
) -> Generator[tuple[list, list], None, None]:
    """
    Valide chaque produit via ProduitImportForm et groupe par lots.
    Yield : (produits_valides, erreurs_du_lot)
    """
    lot_courant: list[dict] = []
    erreurs_courantes: list[str] = []

    for produit_brut in produits_bruts:
        formulaire = ProduitImportForm(data=produit_brut)
        if formulaire.is_valid():
            lot_courant.append(formulaire)
        else:
            msg = f"id_source={produit_brut.get('id_source', '?')} : {formulaire.errors}"
            logger.debug("Produit invalide ignoré : %s", msg)
            erreurs_courantes.append(msg)

        if len(lot_courant) >= taille_lot:
            yield lot_courant, erreurs_courantes
            lot_courant = []
            erreurs_courantes = []

    if lot_courant or erreurs_courantes:
        yield lot_courant, erreurs_courantes


@transaction.atomic
def _persister_lot(
    formulaires_valides: list[ProduitImportForm],
) -> tuple[int, int]:
    """
    Insère ou met à jour un lot de produits validés.

    update_or_create sur id_source (clé naturelle du dataset source).
    Retourne (nb_crees, nb_mis_a_jour).
    """
    nb_crees = nb_mis_a_jour = 0

    # Cache catégories du lot pour minimiser les requêtes get_or_create
    cache_categories: dict[str, CategorieProduit] = {}

    for formulaire in formulaires_valides:
        nom_cat = formulaire.cleaned_data["nom_categorie"]
        if nom_cat not in cache_categories:
            cache_categories[nom_cat] = formulaire.obtenir_ou_creer_categorie()

        categorie = cache_categories[nom_cat]
        donnees_produit = formulaire.to_produit_dict(categorie)

        _, cree = Produit.objects.update_or_create(
            id_source=formulaire.cleaned_data["id_source"],
            defaults=donnees_produit,
        )
        if cree:
            nb_crees += 1
        else:
            nb_mis_a_jour += 1

    return nb_crees, nb_mis_a_jour


def importer_catalogue_fakestore(
    taille_lot: int = None,
    historique: HistoriqueImport = None,
) -> ResultatImport:
    """
    Point d'entrée principal : télécharge et importe le catalogue FakeStore.

    1. Téléchargement JSON
    2. Parsing → générateur de dicts normalisés
    3. Validation par lots via ProduitImportForm
    4. Persistance bulk avec update_or_create
    """
    taille_lot = taille_lot or getattr(settings, "IMPORT_TAILLE_LOT", TAILLE_LOT_DEFAUT)
    resultat = ResultatImport()

    logger.info("Début import FakeStore API : %s", URL_FAKESTORE)

    try:
        donnees_brutes = _telecharger_json(URL_FAKESTORE)
    except ConnectionError as exc:
        message = str(exc)
        logger.error(message)
        if historique:
            historique.marquer_echec(message)
        resultat.erreurs.append(message)
        return resultat

    produits_bruts = parser_fakestore_api(donnees_brutes)

    for formulaires_lot, erreurs_lot in _valider_et_grouper_par_lot(produits_bruts, taille_lot):
        resultat.nb_erreurs += len(erreurs_lot)
        resultat.erreurs.extend(erreurs_lot)

        if formulaires_lot:
            nb_crees, nb_maj = _persister_lot(formulaires_lot)
            resultat.nb_crees += nb_crees
            resultat.nb_mis_a_jour += nb_maj
            resultat.nb_traites += len(formulaires_lot)

        if historique:
            historique.nb_produits_traites = resultat.nb_traites
            historique.nb_produits_crees = resultat.nb_crees
            historique.nb_produits_mis_a_jour = resultat.nb_mis_a_jour
            historique.nb_erreurs = resultat.nb_erreurs
            historique.save(update_fields=[
                "nb_produits_traites", "nb_produits_crees",
                "nb_produits_mis_a_jour", "nb_erreurs",
            ])

    logger.info(
        "Import terminé — traités: %d | créés: %d | MàJ: %d | erreurs: %d",
        resultat.nb_traites, resultat.nb_crees, resultat.nb_mis_a_jour, resultat.nb_erreurs,
    )

    if historique:
        historique.marquer_succes()

    return resultat


def importer_depuis_csv(
    contenu_csv: str,
    taille_lot: int = None,
) -> ResultatImport:
    """Import depuis un CSV uploadé manuellement."""
    taille_lot = taille_lot or getattr(settings, "IMPORT_TAILLE_LOT", TAILLE_LOT_DEFAUT)
    resultat = ResultatImport()

    produits_bruts = parser_csv_generique(contenu_csv)

    for formulaires_lot, erreurs_lot in _valider_et_grouper_par_lot(produits_bruts, taille_lot):
        resultat.nb_erreurs += len(erreurs_lot)
        resultat.erreurs.extend(erreurs_lot)

        if formulaires_lot:
            nb_crees, nb_maj = _persister_lot(formulaires_lot)
            resultat.nb_crees += nb_crees
            resultat.nb_mis_a_jour += nb_maj
            resultat.nb_traites += len(formulaires_lot)

    return resultat
