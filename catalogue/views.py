"""
Vues du catalogue — API JSON pour la recherche de produits.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.generic import View

from .models import CategorieProduit, Produit

logger = logging.getLogger(__name__)


class RechercherProduitsView(View):
    """
    GET /catalogue/rechercher/?q=terme&categorie=slug&prix_max=100

    Retourne une liste de produits au format JSON pour le chatbot.
    """

    NB_MAX_RESULTATS = 10

    def get(self, requete):
        termes = requete.GET.get("q", "").strip()
        slug_categorie = requete.GET.get("categorie", "").strip()
        prix_max = requete.GET.get("prix_max", "").strip()

        produits_qs = Produit.objects.avec_contexte_chatbot().disponibles()

        if termes:
            produits_qs = produits_qs.recherche_plein_texte(termes)

        if slug_categorie:
            produits_qs = produits_qs.par_categorie(slug_categorie)

        if prix_max:
            try:
                produits_qs = produits_qs.filter(prix__lte=Decimal(prix_max))
            except InvalidOperation:
                pass  # Paramètre invalide ignoré silencieusement

        liste_produits = list(produits_qs[: self.NB_MAX_RESULTATS])

        return JsonResponse({
            "produits": [p.to_dict_contexte() for p in liste_produits],
            "total": len(liste_produits),
        })


class ListesCategoriesView(View):
    """GET /catalogue/categories/ — pour peupler les filtres de l'UI."""

    def get(self, requete):
        categories = list(CategorieProduit.objects.all().values("nom", "slug"))
        return JsonResponse({"categories": categories})
