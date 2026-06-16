"""URLs de El Checador (El Taller)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "checador"

urlpatterns = [
    path("", views.tablero, name="tablero"),
    path("checar", views.checar, name="checar"),
    path("visita/nueva", views.visita_modal, name="visita_modal"),
    path("visita", views.visita, name="visita"),
    path("mapa", views.mapa, name="mapa"),
    # Detalle de un registro (chequeo / visita / sesión) en modal HTMX.
    path("jornada/<int:pk>/detalle", views.jornada_detalle, name="jornada_detalle"),
    path("visita/<int:pk>/detalle", views.visita_detalle, name="visita_detalle"),
    path("sesion/<int:pk>/detalle", views.sesion_detalle, name="sesion_detalle"),
    path("timer/iniciar", views.timer_iniciar, name="timer_iniciar"),
    path("timer/detener", views.timer_detener, name="timer_detener"),
    path("sesion/nueva", views.sesion_modal, name="sesion_modal"),
    path("sesion", views.sesion, name="sesion"),
    path("historial/", views.historial, name="historial"),
    path("correccion/nueva", views.correccion_modal, name="correccion_modal"),
    path("correccion", views.correccion, name="correccion"),
    # Ajuste de jornada completa (request del empleado + admin directo) — V1.3
    path("jornada/ajuste/nueva", views.ajuste_jornada_modal, name="ajuste_jornada_modal"),
    path("jornada/ajuste", views.ajuste_jornada, name="ajuste_jornada"),
    path("equipo/<int:usuario_pk>/jornada/editar/modal", views.jornada_admin_modal, name="jornada_admin_modal"),
    path("equipo/<int:usuario_pk>/jornada/editar", views.jornada_admin_editar, name="jornada_admin_editar"),
    path("correcciones/", views.correcciones, name="correcciones"),
    path("correcciones/<int:pk>/resolver/modal", views.correccion_resolver_modal, name="correccion_resolver_modal"),
    path("correcciones/<int:pk>/resolver", views.correccion_resolver, name="correccion_resolver"),
    path("correcciones/<int:pk>/resolver-chat", views.correccion_resolver_chat, name="correccion_resolver_chat"),
    path("equipo/", views.equipo, name="equipo"),
    path("equipo/export", views.equipo_export, name="equipo_export"),
    path("equipo/<int:pk>/", views.equipo_persona, name="equipo_persona"),
    path("api/sync", views.api_sync, name="api_sync"),
]
