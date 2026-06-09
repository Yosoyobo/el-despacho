from django.urls import path

from . import views, views_chat, views_redactor

urlpatterns = [
    # Widget AI 🤖 reusable (S-Chalanes-UX #2): redacta texto en cualquier campo.
    path("chalan/redactar", views_redactor.redactar_texto, name="chalan-redactar"),
    # Chat conversacional (El Chalán) — S-Chalan-Chat-V1.
    path("chalan/", views_chat.chat, name="chalan-chat"),
    path("chalan/c/<int:pk>/", views_chat.conversacion, name="chalan-conversacion"),
    path("chalan/nuevo", views_chat.nuevo, name="chalan-nuevo"),
    path("chalan/c/<int:pk>/enviar", views_chat.enviar, name="chalan-enviar"),
    path("chalan/<int:pk>/aplicar", views_chat.aplicar_accion, name="chalan-aplicar"),
    path("chalan/<int:pk>/cancelar", views_chat.cancelar_accion, name="chalan-cancelar"),
    path("chalan/partial/lista", views_chat.lista, name="chalan-lista"),
    path("chalan/adjunto/<int:pk>", views_chat.adjunto_descargar, name="chalan-adjunto"),
    # El Dictado (flujo clásico de acciones).
    path("dictado/interpretar", views.interpretar_view, name="dictado-interpretar"),
    path("dictado/historial/", views.historial, name="dictado-historial"),
    path("dictado/<int:pk>/preview", views.preview, name="dictado-preview"),
    path("dictado/<int:pk>/aplicar", views.aplicar_view, name="dictado-aplicar"),
    path("dictado/<int:pk>/responder", views.responder_clarificacion, name="dictado-responder"),
    path("dictado/<int:pk>/cancelar", views.cancelar, name="dictado-cancelar"),
    path("dictado/<int:pk>/reintentar", views.reintentar, name="dictado-reintentar"),
    path("dictado/<int:pk>/", views.detalle, name="dictado-detalle"),
]
