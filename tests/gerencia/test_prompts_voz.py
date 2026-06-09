"""UI de Los Prompts (voz editable de Los Chalanes) en La Gerencia.

`/chalanes/prompts/` — super_admin edita; otros roles sin acceso.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _cache_limpio():
    from chalanes.voz import invalidar_cache_voz
    invalidar_cache_voz()
    yield
    invalidar_cache_voz()


def test_get_muestra_slots_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/chalanes/prompts/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Prompt base" in body
    assert "Voz del chat" in body


def test_post_guarda_y_voz_refleja(client, usuario_factory):
    from chalanes.voz import invalidar_cache_voz, voz
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/chalanes/prompts/", {
        "voz_base": "Sé formal y breve.",
        "voz_dictado": "",
        "voz_taller_chat": "Tutea al usuario.",
        "voz_ocr_recibo": "",
        "voz_kpi_dsl": "",
    })
    assert resp.status_code == 302
    invalidar_cache_voz()
    assert voz("base") == "Sé formal y breve."
    assert voz("taller_chat") == "Tutea al usuario."
    assert voz("dictado") == ""


def test_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/chalanes/prompts/")
    assert resp.status_code in (302, 403)


def test_get_muestra_slot_reglas(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/chalanes/prompts/")
    assert resp.status_code == 200
    assert "Reglas operativas" in resp.content.decode()


def test_post_guarda_reglas_operativas(client, usuario_factory):
    from chalanes.voz import invalidar_cache_voz, reglas
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/chalanes/prompts/", {
        "voz_base": "", "voz_dictado": "", "voz_taller_chat": "",
        "voz_ocr_recibo": "", "voz_kpi_dsl": "",
        "voz_reglas_operativas": "Cliente urgente → prioridad 8.",
    })
    assert resp.status_code == 302
    invalidar_cache_voz()
    out = reglas()
    assert "prioridad 8" in out
    assert "REGLAS OPERATIVAS" in out
