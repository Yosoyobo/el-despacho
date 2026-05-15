"""Andamiaje SSO en La Recepción: 404 con mensaje hasta S5.

La Recepción NO tiene `cuentas`/`ajustes`/`django.contrib.auth` instalados
(es un stub minimalista). Las views reales fallarían al importar. Aquí
mostramos un 404 con template propio que explica que esto se habilita en
S5 cuando exista el portal de clientes.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import path


def _no_disponible(request: HttpRequest) -> HttpResponse:
    return render(request, "auth_google/no_disponible.html", status=404)


urlpatterns = [
    path("auth/google/iniciar", _no_disponible, name="iniciar"),
    path("auth/google/callback", _no_disponible, name="callback"),
]
