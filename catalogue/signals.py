"""
Signaux du catalogue.

Signal post_save sur Produit → mise à jour du vecteur full-text.
Utilise update() au lieu de save() pour éviter la récursion infinie
et ne toucher qu'à la colonne vecteur_recherche (O(1) en écriture).
"""
import logging

from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="catalogue.Produit")
def mettre_a_jour_vecteur_recherche(sender, instance, created, **kwargs):
    """
    Recalcule le vecteur full-text après chaque sauvegarde.

    Pondération : nom (poids A=plus important), description (B), marque (C).
    update() direct sur le QS évite de déclencher à nouveau ce signal.
    """
    # Évite la récursion : si le seul champ modifié est vecteur_recherche, on skip
    if not created and hasattr(instance, "_mise_a_jour_vecteur"):
        return

    try:
        vecteur = (
            SearchVector("nom", weight="A", config="french")
            + SearchVector("description", weight="B", config="french")
            + SearchVector("marque", weight="C", config="french")
        )
        # update() SQL direct → pas de signal post_save supplémentaire
        sender.objects.filter(pk=instance.pk).update(vecteur_recherche=vecteur)
    except Exception as exc:
        # Non-bloquant : le produit est sauvé, le vecteur sera recalculé au prochain import
        logger.warning("Échec mise à jour vecteur recherche pk=%s : %s", instance.pk, exc)
