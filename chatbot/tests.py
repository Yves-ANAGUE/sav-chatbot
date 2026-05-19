"""
Tests du chatbot SAV.
"""
import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from catalogue.models import CategorieProduit, Produit
from chatbot.models import ConversationSAV, MessageSAV


def _creer_produit_test(nom="Produit Test", id_source="test_001"):
    categorie, _ = CategorieProduit.objects.get_or_create(
        slug="electronique", defaults={"nom": "Électronique"}
    )
    return Produit.objects.create(
        id_source=id_source,
        nom=nom,
        description="Description test.",
        categorie=categorie,
        prix="29.99",
        quantite_stock=5,
        actif=True,
    )


class TestEnvoyerMessageView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("chatbot:envoyer")
        _creer_produit_test()

    @patch("chatbot.services._appeler_api_anthropic")
    def test_envoi_message_valide(self, mock_api):
        mock_api.return_value = "Voici les produits disponibles..."

        reponse = self.client.post(
            self.url,
            data=json.dumps({"message": "Avez-vous des produits électroniques ?"}),
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()
        self.assertIn("reponse", donnees)
        self.assertIn("conversation_uuid", donnees)
        self.assertEqual(donnees["reponse"], "Voici les produits disponibles...")

    def test_message_vide_retourne_400(self):
        reponse = self.client.post(
            self.url,
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 400)

    def test_corps_invalide_retourne_400(self):
        reponse = self.client.post(
            self.url,
            data="pas du json",
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 400)

    def test_message_trop_long_retourne_400(self):
        reponse = self.client.post(
            self.url,
            data=json.dumps({"message": "x" * 1001}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 400)

    @patch("chatbot.services._appeler_api_anthropic")
    def test_continuite_conversation(self, mock_api):
        """Un uuid_conversation existant doit prolonger la même conversation."""
        mock_api.return_value = "Réponse 1"
        r1 = self.client.post(
            self.url,
            data=json.dumps({"message": "Question 1"}),
            content_type="application/json",
        )
        uuid_conv = r1.json()["conversation_uuid"]

        mock_api.return_value = "Réponse 2"
        r2 = self.client.post(
            self.url,
            data=json.dumps({"message": "Question 2", "conversation_uuid": uuid_conv}),
            content_type="application/json",
        )

        self.assertEqual(r2.json()["conversation_uuid"], uuid_conv)
        conversation = ConversationSAV.objects.get(uuid=uuid_conv)
        self.assertEqual(conversation.messages.count(), 4)  # 2 user + 2 assistant


class TestObtenirHistoriqueView(TestCase):
    def setUp(self):
        self.client = Client()
        self.conversation = ConversationSAV.objects.create()
        MessageSAV.objects.create(
            conversation=self.conversation, role="user", contenu="Bonjour"
        )

    def test_historique_retourne_messages(self):
        url = reverse("chatbot:historique", args=[str(self.conversation.uuid)])
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()
        self.assertEqual(len(donnees["messages"]), 1)
        self.assertEqual(donnees["messages"][0]["contenu"], "Bonjour")

    def test_uuid_inexistant_retourne_404(self):
        import uuid
        url = reverse("chatbot:historique", args=[str(uuid.uuid4())])
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 404)
