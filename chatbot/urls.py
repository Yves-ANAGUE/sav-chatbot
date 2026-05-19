from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.interface_chatbot, name="interface"),
    path("envoyer/", views.envoyer_message, name="envoyer"),
    path("historique/<str:uuid_conversation>/", views.obtenir_historique, name="historique"),
]
