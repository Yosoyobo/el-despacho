"""S-Recados-V2 (C5e): badge del PWA (App Badging API)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_sw_pinta_badge():
    from interfono.sw_js import SERVICE_WORKER_JS
    assert "setAppBadge" in SERVICE_WORKER_JS


def test_shell_sincroniza_badge(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    c = client.get("/recados/").content.decode()
    assert "setAppBadge" in c
    assert "recados_no_leidos_count" not in c  # debe estar interpolado, no literal


def test_shell_sin_badge_anonimo(client):
    # Sin login no se inyecta el script (no hay contadores).
    c = client.get("/recados/").content.decode()
    assert "setAppBadge" not in c
