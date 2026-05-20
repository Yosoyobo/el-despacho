from django.urls import path

from . import views, views_chat

app_name = "recados"

urlpatterns = [
    # ── Chat (nuevo default, sprint S-Recados-Chat) ─────────────────────────
    path("", views_chat.bandeja, name="bandeja"),
    path("partials/bandeja", views_chat.partial_bandeja, name="partial_bandeja"),
    path("nueva/", views_chat.nueva, name="nueva"),
    path("c/<int:pk>/", views_chat.conversacion, name="conversacion"),
    path("c/<int:pk>/mensajes", views_chat.partial_mensajes, name="partial_mensajes"),
    path("c/<int:pk>/enviar", views_chat.enviar, name="enviar"),
    path("c/<int:pk>/leido", views_chat.marcar_leido, name="leido_conv"),

    # ── Bandeja legacy (Recados S2b.1) ──────────────────────────────────────
    path("legacy/", views.bandeja, name="legacy_bandeja"),
    path("legacy/nuevo/", views.nuevo, name="legacy_nuevo"),
    path("legacy/<int:pk>/", views.detalle, name="legacy_detalle"),
    path("legacy/<int:pk>/editar/", views.editar, name="legacy_editar"),
    path("legacy/<int:pk>/leido/", views.marcar_leido, name="legacy_marcar_leido"),
]
