"""S-Finanzas-UX: el selector de Formato de hora se mudó de «Mis notificaciones»
(El Taller) a La Gerencia → Catálogos → Horarios laborales. Es una preferencia
personal (cada usuario elige la suya) que aplica a TODAS las horas del sistema.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_horarios_muestra_formato_hora(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/catalogos/horarios/")
    assert resp.status_code == 200
    assert "Formato de hora" in resp.content.decode()


def test_guardar_formato_hora_gerencia(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogos/horarios/formato-hora/", {"formato_hora": "ampm"})
    assert resp.status_code == 302
    u.refresh_from_db()
    assert u.formato_hora == "ampm"


def test_guardar_formato_hora_invalido(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/catalogos/horarios/formato-hora/", {"formato_hora": "xx"})
    assert resp.status_code == 302
    u.refresh_from_db()
    assert u.formato_hora == "24h"  # sin cambio ante valor inválido
