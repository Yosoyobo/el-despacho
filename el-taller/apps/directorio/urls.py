from django.urls import path

from . import views

urlpatterns = [
    path("directorio/", views.lista, name="directorio-lista"),
    path("directorio/<int:pk>/", views.perfil, name="directorio-perfil"),
    # Sprint de pendientes 2026-09-28: el recuadro «Quién está conectado» del
    # Dashboard. Se refresca solo, así que es SONDEO: está en
    # lib.presencia.URL_NAMES_SONDEO y no cuenta como actividad.
    path("directorio/en-linea/", views.en_linea, name="directorio-en-linea"),
]
