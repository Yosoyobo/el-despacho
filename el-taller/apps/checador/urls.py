"""URLs de El Checador (El Taller)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "checador"

urlpatterns = [
    path("", views.tablero, name="tablero"),
    path("checar", views.checar, name="checar"),
]
