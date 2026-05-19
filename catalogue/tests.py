"""
Tests unitaires — parseurs et service d'import.

Testables sans base de données (TestCase simple pour les parseurs).
Tests d'intégration avec base pour le service d'import.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase

from catalogue.parseurs import (
    _nettoyer_prix,
    _nettoyer_chaine,
    parser_fakestore_api,
    parser_csv_generique,
)
from catalogue.serializers import ProduitImportForm


# ── Tests parseurs (pas de DB) ──

class TestNettoyerPrix(TestCase):
    """_nettoyer_prix doit gérer tous les formats de prix courants."""

    def test_decimal_brut(self):
        self.assertEqual(_nettoyer_prix(29.99), Decimal("29.99"))

    def test_chaine_avec_symbole_dollar(self):
        self.assertEqual(_nettoyer_prix("$29.99"), Decimal("29.99"))

    def test_chaine_avec_symbole_euro(self):
        self.assertEqual(_nettoyer_prix("29,99€"), Decimal("29.99"))

    def test_valeur_none(self):
        self.assertEqual(_nettoyer_prix(None), Decimal("0.00"))

    def test_chaine_invalide(self):
        self.assertEqual(_nettoyer_prix("gratuit"), Decimal("0.00"))

    def test_zero(self):
        self.assertEqual(_nettoyer_prix(0), Decimal("0.00"))


class TestNettoyerChaine(TestCase):
    def test_suppression_espaces(self):
        self.assertEqual(_nettoyer_chaine("  bonjour  "), "bonjour")

    def test_troncature(self):
        self.assertEqual(_nettoyer_chaine("abcdef", longueur_max=3), "abc")

    def test_none_retourne_chaine_vide(self):
        self.assertEqual(_nettoyer_chaine(None), "")


class TestParserFakestoreApi(TestCase):
    """parser_fakestore_api doit normaliser la structure FakeStore."""

    DONNEES_EXEMPLE = [
        {
            "id": 1,
            "title": "Fjallraven - Foldsack No. 1 Backpack",
            "price": 109.95,
            "description": "Your perfect pack for everyday use.",
            "category": "men's clothing",
            "image": "https://fakestoreapi.com/img/81fAn.jpg",
            "rating": {"rate": 3.9, "count": 120},
        }
    ]

    def test_structure_normalisee(self):
        resultats = list(parser_fakestore_api(self.DONNEES_EXEMPLE))
        self.assertEqual(len(resultats), 1)
        produit = resultats[0]

        self.assertEqual(produit["id_source"], "fakestore_1")
        self.assertEqual(produit["prix"], Decimal("109.95"))
        self.assertEqual(produit["note_moyenne"], Decimal("3.90"))
        self.assertEqual(produit["nombre_avis"], 120)
        self.assertEqual(produit["nom_categorie"], "Men'S Clothing")

    def test_liste_vide(self):
        resultats = list(parser_fakestore_api([]))
        self.assertEqual(resultats, [])

    def test_champs_manquants(self):
        """Un produit sans rating ne doit pas lever d'exception."""
        donnees = [{"id": 2, "title": "Test", "price": 9.99, "category": "test"}]
        resultats = list(parser_fakestore_api(donnees))
        self.assertEqual(len(resultats), 1)
        self.assertIsNone(resultats[0]["note_moyenne"])


class TestParserCsvGenerique(TestCase):
    """parser_csv_generique doit supporter les colonnes en français et anglais."""

    CSV_FRANCAIS = """id_source,nom,description,categorie,prix,stock
prod_1,Écouteurs BT,Son cristallin,Électronique,49.99,15
prod_2,Clavier mécanique,,Informatique,89.00,3"""

    CSV_ANGLAIS = """id,name,description,category,price,quantity
1,Wireless Mouse,Ergonomic design,Electronics,29.99,50"""

    def test_csv_francais(self):
        resultats = list(parser_csv_generique(self.CSV_FRANCAIS))
        self.assertEqual(len(resultats), 2)
        self.assertEqual(resultats[0]["nom"], "Écouteurs BT")
        self.assertEqual(resultats[0]["prix"], Decimal("49.99"))
        self.assertEqual(resultats[0]["quantite_stock"], 15)

    def test_csv_anglais(self):
        resultats = list(parser_csv_generique(self.CSV_ANGLAIS))
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["nom"], "Wireless Mouse")

    def test_csv_vide(self):
        resultats = list(parser_csv_generique(""))
        self.assertEqual(resultats, [])


# ── Tests formulaire de validation ──

class TestProduitImportForm(TestCase):
    """ProduitImportForm doit valider et rejeter les données invalides."""

    DONNEES_VALIDES = {
        "id_source": "test_001",
        "nom": "Casque Audio Pro",
        "description": "Qualité studio.",
        "marque": "SoundMax",
        "nom_categorie": "Électronique",
        "prix": "149.99",
        "note_moyenne": "4.5",
        "nombre_avis": "320",
        "quantite_stock": "8",
        "attributs": "{}",
        "image_url": "https://example.com/casque.jpg",
    }

    def test_donnees_valides(self):
        form = ProduitImportForm(data=self.DONNEES_VALIDES)
        self.assertTrue(form.is_valid(), form.errors)

    def test_nom_vide_invalide(self):
        donnees = {**self.DONNEES_VALIDES, "nom": "   "}
        form = ProduitImportForm(data=donnees)
        self.assertFalse(form.is_valid())
        self.assertIn("nom", form.errors)

    def test_prix_negatif_invalide(self):
        donnees = {**self.DONNEES_VALIDES, "prix": "-10.00"}
        form = ProduitImportForm(data=donnees)
        self.assertFalse(form.is_valid())

    def test_note_hors_plage_invalide(self):
        donnees = {**self.DONNEES_VALIDES, "note_moyenne": "6.0"}
        form = ProduitImportForm(data=donnees)
        self.assertFalse(form.is_valid())

    def test_image_url_vide_acceptee(self):
        donnees = {**self.DONNEES_VALIDES, "image_url": ""}
        form = ProduitImportForm(data=donnees)
        self.assertTrue(form.is_valid(), form.errors)
