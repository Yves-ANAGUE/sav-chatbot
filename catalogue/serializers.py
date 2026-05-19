"""
Serializers de validation pour l'import du catalogue.

Utilise des forms Django plutôt que DRF pour éviter la dépendance externe.
Chaque champ est validé et normalisé avant insertion en base.
"""
import logging
from decimal import Decimal

from django import forms
from django.utils.text import slugify

from .models import CategorieProduit, Produit

logger = logging.getLogger(__name__)


class ProduitImportForm(forms.Form):
    """
    Valide et normalise un produit brut issu d'un parseur.
    Retourne des données prêtes pour bulk_create/update_or_create.
    """

    id_source = forms.CharField(max_length=100)
    nom = forms.CharField(max_length=300)
    description = forms.CharField(required=False, initial="")
    marque = forms.CharField(max_length=150, required=False, initial="")
    nom_categorie = forms.CharField(max_length=100)
    prix = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.00")
    )
    note_moyenne = forms.DecimalField(
        max_digits=3, decimal_places=1,
        min_value=Decimal("0.0"), max_value=Decimal("5.0"),
        required=False,
    )
    nombre_avis = forms.IntegerField(min_value=0, initial=0)
    quantite_stock = forms.IntegerField(min_value=0, initial=0)
    attributs = forms.JSONField(required=False, initial=dict)
    image_url = forms.URLField(max_length=500, required=False, initial="")

    def clean_nom(self) -> str:
        nom = self.cleaned_data["nom"].strip()
        if not nom:
            raise forms.ValidationError("Le nom du produit est obligatoire.")
        return nom

    def clean_id_source(self) -> str:
        id_source = self.cleaned_data["id_source"].strip()
        if not id_source:
            raise forms.ValidationError("L'identifiant source est obligatoire.")
        return id_source

    def clean_image_url(self) -> str:
        """Accepte les URLs vides (champ optionnel)."""
        url = self.cleaned_data.get("image_url", "")
        return url or ""

    def clean_attributs(self) -> dict:
        """S'assure que attributs est toujours un dict."""
        attributs = self.cleaned_data.get("attributs") or {}
        if not isinstance(attributs, dict):
            return {}
        return attributs

    def obtenir_ou_creer_categorie(self) -> CategorieProduit:
        """
        Retourne la catégorie existante ou la crée.
        Utilise get_or_create pour éviter les race conditions en import concurrent.
        """
        nom_categorie = self.cleaned_data["nom_categorie"]
        slug = slugify(nom_categorie)[:110]
        categorie, _ = CategorieProduit.objects.get_or_create(
            slug=slug,
            defaults={"nom": nom_categorie},
        )
        return categorie

    def to_produit_dict(self, categorie: CategorieProduit) -> dict:
        """Construit le dict d'initialisation du modèle Produit."""
        donnees = self.cleaned_data
        return {
            "nom": donnees["nom"],
            "description": donnees.get("description", ""),
            "marque": donnees.get("marque", ""),
            "categorie": categorie,
            "prix": donnees["prix"],
            "note_moyenne": donnees.get("note_moyenne"),
            "nombre_avis": donnees.get("nombre_avis", 0),
            "quantite_stock": donnees.get("quantite_stock", 0),
            "attributs": donnees.get("attributs", {}),
            "image_url": donnees.get("image_url", ""),
        }
