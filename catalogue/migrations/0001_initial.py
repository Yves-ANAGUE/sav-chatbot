"""
Migration initiale du catalogue.
Crée les tables CategorieProduit, Produit et HistoriqueImport
avec les index GIN pour la recherche full-text.
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CategorieProduit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("nom", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=110, unique=True)),
                ("description", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Catégorie",
                "verbose_name_plural": "Catégories",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="Produit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("id_source", models.CharField(db_index=True, max_length=100, unique=True)),
                ("nom", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True)),
                ("marque", models.CharField(blank=True, max_length=150)),
                (
                    "categorie",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="produits",
                        to="catalogue.categorieproduit",
                    ),
                ),
                ("prix", models.DecimalField(decimal_places=2, default="0.00", max_digits=10)),
                ("prix_solde", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("note_moyenne", models.DecimalField(blank=True, decimal_places=1, max_digits=3, null=True)),
                ("nombre_avis", models.PositiveIntegerField(default=0)),
                ("quantite_stock", models.PositiveIntegerField(default=0)),
                ("attributs", models.JSONField(blank=True, default=dict)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("actif", models.BooleanField(default=True)),
                ("vecteur_recherche", SearchVectorField(blank=True, null=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Produit",
                "verbose_name_plural": "Produits",
                "ordering": ["-note_moyenne", "nom"],
            },
        ),
        migrations.AddIndex(
            model_name="produit",
            index=GinIndex(fields=["vecteur_recherche"], name="idx_produit_fts"),
        ),
        migrations.AddIndex(
            model_name="produit",
            index=models.Index(fields=["prix"], name="idx_produit_prix"),
        ),
        migrations.AddIndex(
            model_name="produit",
            index=models.Index(
                fields=["categorie", "actif", "quantite_stock"],
                name="idx_produit_cat_dispo",
            ),
        ),
        migrations.CreateModel(
            name="HistoriqueImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("source_url", models.URLField(max_length=500)),
                (
                    "statut",
                    models.CharField(
                        choices=[("en_cours", "En cours"), ("succes", "Succès"), ("echec", "Échec")],
                        default="en_cours",
                        max_length=20,
                    ),
                ),
                ("nb_produits_traites", models.PositiveIntegerField(default=0)),
                ("nb_produits_crees", models.PositiveIntegerField(default=0)),
                ("nb_produits_mis_a_jour", models.PositiveIntegerField(default=0)),
                ("nb_erreurs", models.PositiveIntegerField(default=0)),
                ("message_erreur", models.TextField(blank=True)),
                ("debut_le", models.DateTimeField(default=django.utils.timezone.now)),
                ("fin_le", models.DateTimeField(null=True, blank=True)),
            ],
            options={
                "verbose_name": "Historique d'import",
                "verbose_name_plural": "Historiques d'import",
                "ordering": ["-debut_le"],
            },
        ),
    ]
