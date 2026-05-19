from django.apps import AppConfig


class CatalogueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalogue"
    verbose_name = "Catalogue Produits"

    def ready(self):
        # Enregistrement des signaux au démarrage de l'application
        import catalogue.signals  # noqa: F401
