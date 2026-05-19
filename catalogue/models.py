"""
Modèles du catalogue produits.

Choix d'architecture :
- SearchVectorField pré-calculé via signal → recherche full-text O(log n) avec index GIN
- JSONField pour attributs variables (évite le schéma rigide par catégorie)
- DecimalField pour prix (précision exacte, pas de drift float)
"""
import logging
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class CategorieProduit(models.Model):
    """Hiérarchie plate des catégories — un niveau suffit pour ce dataset."""

    nom = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom


class ProduitQuerySet(models.QuerySet):
    """QuerySet métier — encapsule la logique de filtrage réutilisable."""

    def disponibles(self) -> "ProduitQuerySet":
        """Filtre les produits en stock et actifs."""
        return self.filter(actif=True, quantite_stock__gt=0)

    def par_categorie(self, slug_categorie: str) -> "ProduitQuerySet":
        return self.filter(categorie__slug=slug_categorie)

    def recherche_plein_texte(self, termes: str) -> "ProduitQuerySet":
        """
        Recherche full-text PostgreSQL via vecteur pré-calculé.
        Fallback ILIKE si le vecteur est vide (données fraîchement insérées).
        """
        if not termes.strip():
            return self.none()

        resultats = self.filter(vecteur_recherche=termes)
        if not resultats.exists():
            # Fallback pour données sans vecteur calculé
            resultats = self.filter(
                Q(nom__icontains=termes) | Q(description__icontains=termes)
            )
        return resultats

    def avec_contexte_chatbot(self) -> "ProduitQuerySet":
        """Sélection optimisée des champs utiles au chatbot (évite SELECT *)."""
        return self.select_related("categorie").only(
            "id", "nom", "description", "prix", "note_moyenne",
            "quantite_stock", "marque", "categorie__nom",
        )


class ProduitManager(models.Manager):
    """
    Manager principal — retourne ProduitQuerySet pour exposer
    toutes les méthodes métier directement sur Produit.objects.
    """

    def get_queryset(self) -> ProduitQuerySet:
        return ProduitQuerySet(self.model, using=self._db)

    # Délégation explicite de chaque méthode métier du QuerySet

    def disponibles(self) -> ProduitQuerySet:
        return self.get_queryset().disponibles()

    def recherche_plein_texte(self, termes: str) -> ProduitQuerySet:
        return self.get_queryset().recherche_plein_texte(termes)

    def avec_contexte_chatbot(self) -> ProduitQuerySet:
        # Manquait dans la version initiale — causait AttributeError au premier message
        return self.get_queryset().avec_contexte_chatbot()

    def par_categorie(self, slug_categorie: str) -> ProduitQuerySet:
        return self.get_queryset().par_categorie(slug_categorie)


class Produit(models.Model):
    """
    Produit du catalogue importé depuis FakeStore API.

    Indexation full-text sur (nom + description + marque) via GIN.
    """

    # Identifiant source pour idempotence de l'import
    id_source = models.CharField(max_length=100, unique=True, db_index=True)

    nom = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    marque = models.CharField(max_length=150, blank=True)
    categorie = models.ForeignKey(
        CategorieProduit,
        on_delete=models.PROTECT,
        related_name="produits",
    )

    # Décimal pour prix — jamais de float pour les données monétaires
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    prix_solde = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    note_moyenne = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    nombre_avis = models.PositiveIntegerField(default=0)
    quantite_stock = models.PositiveIntegerField(default=0)

    # Attributs variables par catégorie (couleurs, tailles, specs techniques…)
    # JSONField évite 20+ colonnes nullables avec complexité de schéma O(1) à la lecture
    attributs = models.JSONField(default=dict, blank=True)

    image_url = models.URLField(max_length=500, blank=True)
    actif = models.BooleanField(default=True)

    # Vecteur pré-calculé — mis à jour via signal post_save
    # Permet recherche full-text O(log n) avec index GIN
    vecteur_recherche = SearchVectorField(null=True, blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    objects = ProduitManager()

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ["-note_moyenne", "nom"]
        indexes = [
            # GIN sur vecteur full-text — crucial pour perfs de recherche
            GinIndex(fields=["vecteur_recherche"], name="idx_produit_fts"),
            # B-tree sur prix pour filtres de plage
            models.Index(fields=["prix"], name="idx_produit_prix"),
            # Index composite pour la recherche par catégorie + disponibilité
            models.Index(
                fields=["categorie", "actif", "quantite_stock"],
                name="idx_produit_cat_dispo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nom} ({self.categorie})"

    @property
    def en_stock(self) -> bool:
        return self.actif and self.quantite_stock > 0

    @property
    def prix_actuel(self) -> Decimal:
        """Retourne le prix soldé si disponible."""
        return self.prix_solde if self.prix_solde else self.prix

    def to_dict_contexte(self) -> dict:
        """
        Sérialisation légère pour injection dans le prompt du chatbot.
        Intentionnellement limité aux champs pertinents SAV.
        """
        return {
            "id": self.id,
            "nom": self.nom,
            "categorie": self.categorie.nom if self.categorie_id else "N/A",
            "prix": float(self.prix_actuel),
            "note": float(self.note_moyenne) if self.note_moyenne else None,
            "en_stock": self.en_stock,
            "description": self.description[:300] if self.description else "",
            "attributs": self.attributs,
        }


class HistoriqueImport(models.Model):
    """Traçabilité des imports — permet de rejouer ou auditer."""

    class StatutImport(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        SUCCES = "succes", "Succès"
        ECHEC = "echec", "Échec"

    source_url = models.URLField(max_length=500)
    statut = models.CharField(
        max_length=20,
        choices=StatutImport.choices,
        default=StatutImport.EN_COURS,
    )
    nb_produits_traites = models.PositiveIntegerField(default=0)
    nb_produits_crees = models.PositiveIntegerField(default=0)
    nb_produits_mis_a_jour = models.PositiveIntegerField(default=0)
    nb_erreurs = models.PositiveIntegerField(default=0)
    message_erreur = models.TextField(blank=True)
    debut_le = models.DateTimeField(default=timezone.now)
    fin_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Historique d'import"
        verbose_name_plural = "Historiques d'import"
        ordering = ["-debut_le"]

    def __str__(self) -> str:
        return f"Import {self.debut_le:%Y-%m-%d %H:%M} — {self.statut}"

    def marquer_succes(self) -> None:
        self.statut = self.StatutImport.SUCCES
        self.fin_le = timezone.now()
        self.save(update_fields=["statut", "fin_le"])

    def marquer_echec(self, message: str) -> None:
        self.statut = self.StatutImport.ECHEC
        self.message_erreur = message
        self.fin_le = timezone.now()
        self.save(update_fields=["statut", "message_erreur", "fin_le"])
