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
    path("timer/iniciar", views.timer_iniciar, name="timer_iniciar"),
    path("timer/detener", views.timer_detener, name="timer_detener"),
    path("sesion/nueva", views.sesion_modal, name="sesion_modal"),
    path("sesion", views.sesion, name="sesion"),
    path("historial/", views.historial, name="historial"),
]
