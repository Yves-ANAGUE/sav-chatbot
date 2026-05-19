"""
Modèles du chatbot SAV.

ConversationSAV : session de chat avec historique complet.
MessageSAV : message individuel avec les produits référencés.
"""
import uuid

from django.db import models

from catalogue.models import Produit


class ConversationSAV(models.Model):
    """Session de conversation — identifiée par UUID côté client."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation SAV"
        verbose_name_plural = "Conversations SAV"
        ordering = ["-modifie_le"]

    def __str__(self) -> str:
        return f"Conversation {self.uuid} ({self.messages.count()} messages)"

    def historique_formate(self) -> list[dict]:
        """
        Retourne l'historique au format attendu par l'API Anthropic :
        [{"role": "user"|"assistant", "content": "..."}]
        """
        return [
            {"role": msg.role, "content": msg.contenu}
            for msg in self.messages.order_by("cree_le")
        ]


class MessageSAV(models.Model):
    """Message individuel dans une conversation SAV."""

    class Role(models.TextChoices):
        UTILISATEUR = "user", "Utilisateur"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        ConversationSAV,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    contenu = models.TextField()

    # Produits référencés dans ce message (pour traçabilité et analytics)
    produits_references = models.ManyToManyField(
        Produit,
        blank=True,
        related_name="messages_sav",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message SAV"
        verbose_name_plural = "Messages SAV"
        ordering = ["cree_le"]

    def __str__(self) -> str:
        return f"[{self.role}] {self.contenu[:60]}"
