from django.contrib import admin
from django.utils.html import format_html

from .models import CategorieProduit, HistoriqueImport, Produit


@admin.register(CategorieProduit)
class CategorieProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "slug", "nb_produits")
    prepopulated_fields = {"slug": ("nom",)}
    search_fields = ("nom",)

    def nb_produits(self, obj):
        return obj.produits.count()
    nb_produits.short_description = "Nb produits"


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = (
        "nom", "categorie", "prix_formate", "note_moyenne",
        "quantite_stock", "actif", "miniature"
    )
    list_filter = ("categorie", "actif")
    search_fields = ("nom", "description", "marque", "id_source")
    readonly_fields = ("id_source", "vecteur_recherche", "cree_le", "modifie_le")
    list_per_page = 50

    def prix_formate(self, obj):
        return f"{obj.prix_actuel} €"
    prix_formate.short_description = "Prix"

    def miniature(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-height:40px;" />', obj.image_url
            )
        return "—"
    miniature.short_description = "Image"


@admin.register(HistoriqueImport)
class HistoriqueImportAdmin(admin.ModelAdmin):
    list_display = (
        "debut_le", "statut", "source_url_courte",
        "nb_produits_crees", "nb_produits_mis_a_jour", "nb_erreurs"
    )
    list_filter = ("statut",)
    readonly_fields = (
        "source_url", "statut", "nb_produits_traites", "nb_produits_crees",
        "nb_produits_mis_a_jour", "nb_erreurs", "message_erreur",
        "debut_le", "fin_le",
    )

    def source_url_courte(self, obj):
        return obj.source_url[:60]
    source_url_courte.short_description = "Source"

    def has_add_permission(self, request):
        return False  # Import géré uniquement via commande
