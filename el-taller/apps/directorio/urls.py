from django.urls import path

from cuentas.historial_views import vista_persona, vista_propia

from . import views

urlpatterns = [
    path("directorio/", views.lista, name="directorio-lista"),
    path("directorio/<int:pk>/", views.perfil, name="directorio-perfil"),
    # 2026-09-29: el historial de actividad (vista compartida en cuentas/). El de
    # otro pide `equipo.ver_historial`; el propio, nada.
    path("directorio/<int:pk>/actividad/", vista_persona("historial/actividad.html"),
         name="directorio-actividad"),
    path("perfil/actividad/", vista_propia("historial/actividad.html"), name="perfil-actividad"),
    # Sprint de pendientes 2026-09-28: el recuadro «Quién está conectado» del
    # Dashboard. Se refresca solo, así que es SONDEO: está en
    # lib.presencia.URL_NAMES_SONDEO y no cuenta como actividad.
    path("directorio/en-linea/", views.en_linea, name="directorio-en-linea"),
]
