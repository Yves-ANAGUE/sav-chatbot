from django.urls import path
from .views import ListesCategoriesView, RechercherProduitsView

app_name = "catalogue"

urlpatterns = [
    path("rechercher/", RechercherProduitsView.as_view(), name="rechercher"),
    path("categories/", ListesCategoriesView.as_view(), name="categories"),
]
