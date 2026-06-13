from django.urls import path

from . import views

urlpatterns = [
    path("directorio/", views.lista, name="directorio-lista"),
    path("directorio/<int:pk>/", views.perfil, name="directorio-perfil"),
]
