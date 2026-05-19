from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("catalogue/", include("catalogue.urls", namespace="catalogue")),
    path("chatbot/", include("chatbot.urls", namespace="chatbot")),
    path("", include("chatbot.urls", namespace="chatbot_racine")),
]
