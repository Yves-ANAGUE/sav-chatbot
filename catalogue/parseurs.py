"""
Parseurs de données pour l'import du catalogue.

Principe : chaque parseur est une fonction pure qui transforme
une structure brute en dict normalisé attendu par le serializer.
Isolé de Django → testable unitairement sans base de données.
"""
import csv
import io
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Generator
from decimal import ROUND_HALF_UP

logger = logging.getLogger(__name__)

# Schéma de sortie attendu par ProduitImportSerializer
CHAMPS_PRODUIT_NORMALISE = frozenset([
    "id_source", "nom", "description", "marque", "nom_categorie",
    "prix", "note_moyenne", "nombre_avis", "quantite_stock",
    "attributs", "image_url",
])


def _nettoyer_prix(valeur_brute) -> Decimal:
    """
    Extrait un Decimal depuis des formats variés : "$29.99", "29,99€", 29.99.
    Retourne Decimal("0.00") si non parsable — non bloquant intentionnellement.
    """
    if valeur_brute is None:
        return Decimal("0.00")
    chaine = re.sub(r"[^\d.,]", "", str(valeur_brute)).replace(",", ".")
    try:
        return Decimal(chaine).quantize(Decimal("0.01"))
    except InvalidOperation:
        logger.debug("Prix non parsable : %r → 0.00", valeur_brute)
        return Decimal("0.00")
    
def _nettoyer_note(valeur_brute) -> Decimal | None:
    """
    Convertit une note en Decimal avec 1 seule décimale.
    Retourne None si invalide.
    """
    if valeur_brute is None:
        return None
    try:
        return Decimal(str(valeur_brute)).quantize(Decimal("0.0"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        logger.debug("Note non parsable : %r → None", valeur_brute)
        return None


def _nettoyer_chaine(valeur, longueur_max: int = None) -> str:
    """Normalise et tronque une chaîne de caractères."""
    if valeur is None:
        return ""
    nettoyee = str(valeur).strip()
    return nettoyee[:longueur_max] if longueur_max else nettoyee


def parser_fakestore_api(donnees_json: list[dict]) -> Generator[dict, None, None]:
    """
    Parse la réponse JSON de https://fakestoreapi.com/products.

    Structure source :
    {
        "id": 1, "title": "...", "price": 109.95,
        "description": "...", "category": "electronics",
        "image": "https://...",
        "rating": {"rate": 3.9, "count": 120}
    }
    """
    for item in donnees_json:
        note_brute = item.get("rating", {})
        yield {
            "id_source": f"fakestore_{item.get('id', '')}",
            "nom": _nettoyer_chaine(item.get("title"), 300),
            "description": _nettoyer_chaine(item.get("description")),
            "marque": "",  # FakeStore n'a pas de marque
            "nom_categorie": _nettoyer_chaine(item.get("category"), 100).title(),
            "prix": _nettoyer_prix(item.get("price")),
            "note_moyenne": _nettoyer_note(note_brute.get("rate")) if note_brute else None,
            "nombre_avis": int(note_brute.get("count", 0)) if note_brute else 0,
            "quantite_stock": 10,  # FakeStore ne fournit pas le stock
            "attributs": {},
            "image_url": _nettoyer_chaine(item.get("image"), 500),
        }


def parser_csv_generique(contenu_csv: str) -> Generator[dict, None, None]:
    """
    Parse un CSV avec les colonnes minimales :
    id_source, nom, description, categorie, prix, [marque, stock, image_url, note]

    Robuste aux colonnes manquantes via .get() avec valeurs par défaut.
    """
    lecteur = csv.DictReader(io.StringIO(contenu_csv))

    # Normalisation des noms de colonnes (insensible à la casse et aux espaces)
    if not lecteur.fieldnames:
        logger.warning("CSV vide ou sans en-têtes")
        return

    for numero_ligne, ligne in enumerate(lecteur, start=2):
        try:
            yield {
                "id_source": _nettoyer_chaine(
                    ligne.get("id_source") or ligne.get("id") or f"csv_{numero_ligne}",
                    100,
                ),
                "nom": _nettoyer_chaine(
                    ligne.get("nom") or ligne.get("name") or ligne.get("title"), 300
                ),
                "description": _nettoyer_chaine(
                    ligne.get("description") or ligne.get("desc")
                ),
                "marque": _nettoyer_chaine(
                    ligne.get("marque") or ligne.get("brand"), 150
                ),
                "nom_categorie": _nettoyer_chaine(
                    ligne.get("categorie") or ligne.get("category") or "Divers", 100
                ).title(),
                "prix": _nettoyer_prix(ligne.get("prix") or ligne.get("price")),
                "note_moyenne": _nettoyer_prix(
                    ligne.get("note") or ligne.get("rating")
                ) or None,
                "nombre_avis": int(ligne.get("avis") or ligne.get("reviews") or 0),
                "quantite_stock": int(ligne.get("stock") or ligne.get("quantity") or 0),
                "attributs": {},
                "image_url": _nettoyer_chaine(
                    ligne.get("image_url") or ligne.get("image"), 500
                ),
            }
        except (ValueError, TypeError) as exc:
            logger.warning("Ligne %d ignorée : %s", numero_ligne, exc)
            continue


def parser_open_food_facts(donnees_json: dict) -> Generator[dict, None, None]:
    """
    Parse le format Open Food Facts (products array).
    Extrait les champs SAV pertinents depuis la structure dense.
    """
    produits = donnees_json.get("products", [])
    for item in produits:
        if not item.get("product_name"):
            continue  # Produits sans nom inutilisables

        yield {
            "id_source": f"off_{item.get('code', item.get('_id', ''))}",
            "nom": _nettoyer_chaine(item.get("product_name"), 300),
            "description": _nettoyer_chaine(item.get("generic_name")),
            "marque": _nettoyer_chaine(item.get("brands"), 150),
            "nom_categorie": _nettoyer_chaine(
                item.get("categories", "Alimentation").split(",")[0], 100
            ).strip().title(),
            "prix": Decimal("0.00"),  # OFF ne fournit pas de prix
            "note_moyenne": None,
            "nombre_avis": 0,
            "quantite_stock": 1,
            "attributs": {
                "nutriscore": item.get("nutriscore_grade"),
                "ingredients": item.get("ingredients_text", "")[:500],
                "allergenes": item.get("allergens", ""),
            },
            "image_url": _nettoyer_chaine(item.get("image_url"), 500),
        }
