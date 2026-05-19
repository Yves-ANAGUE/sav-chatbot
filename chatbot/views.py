"""
Vues du chatbot SAV.

Endpoint AJAX principal : POST /chatbot/envoyer/
Endpoint historique : GET /chatbot/conversation/<uuid>/
"""
import json
import logging
import uuid

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from .models import ConversationSAV, MessageSAV
from .services import generer_reponse_sav

logger = logging.getLogger(__name__)


def interface_chatbot(requete):
    """Vue principale — rendu de l'interface de chat."""
    return render(requete, "chatbot/interface.html")


@require_http_methods(["POST"])
def envoyer_message(requete):
    """
    Endpoint AJAX pour envoyer un message et recevoir la réponse du bot.

    Corps JSON attendu :
    {
        "message": "Avez-vous des écouteurs bluetooth ?",
        "conversation_uuid": "..." (optionnel, créé si absent)
    }
    """
    try:
        corps = json.loads(requete.body)
    except json.JSONDecodeError:
        return JsonResponse({"erreur": "Corps JSON invalide"}, status=400)

    message_utilisateur = corps.get("message", "").strip()
    if not message_utilisateur:
        return JsonResponse({"erreur": "Message vide"}, status=400)

    if len(message_utilisateur) > 1000:
        return JsonResponse({"erreur": "Message trop long (max 1000 caractères)"}, status=400)

    # Récupère ou crée la conversation
    uuid_conversation = corps.get("conversation_uuid")
    if uuid_conversation:
        try:
            conversation = get_object_or_404(ConversationSAV, uuid=uuid_conversation)
        except (ValueError, ConversationSAV.DoesNotExist):
            conversation = ConversationSAV.objects.create()
    else:
        conversation = ConversationSAV.objects.create()

    # Historique pour le contexte multi-tours
    historique = conversation.historique_formate()

    # Génération de la réponse IA avec contexte produit (RAG)
    reponse_texte, produits_references = generer_reponse_sav(
        message_utilisateur, historique
    )

    # Persistance des deux messages
    message_user = MessageSAV.objects.create(
        conversation=conversation,
        role=MessageSAV.Role.UTILISATEUR,
        contenu=message_utilisateur,
    )

    message_bot = MessageSAV.objects.create(
        conversation=conversation,
        role=MessageSAV.Role.ASSISTANT,
        contenu=reponse_texte,
    )

    if produits_references:
        message_bot.produits_references.set(produits_references)

    return JsonResponse({
        "reponse": reponse_texte,
        "conversation_uuid": str(conversation.uuid),
        "produits_references": [p.to_dict_contexte() for p in produits_references],
    })


@require_http_methods(["GET"])
def obtenir_historique(requete, uuid_conversation: str):
    """Retourne l'historique d'une conversation pour restauration côté client."""
    try:
        conversation = get_object_or_404(ConversationSAV, uuid=uuid_conversation)
    except ValueError:
        return JsonResponse({"erreur": "UUID invalide"}, status=400)

    messages = [
        {
            "role": msg.role,
            "contenu": msg.contenu,
            "horodatage": msg.cree_le.isoformat(),
        }
        for msg in conversation.messages.order_by("cree_le")
    ]

    return JsonResponse({
        "conversation_uuid": str(conversation.uuid),
        "messages": messages,
    })
