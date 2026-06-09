"""Voz/estilo personal del usuario con El Chalán (capa aditiva).

`/perfil/chalanes/voz` guarda `Usuario.voz_chalan`; `preludio(estacion, usuario)`
la concatena después de la voz institucional. Solo afecta tono — nunca permisos.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_post_voz_personal_guarda_en_usuario(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/perfil/chalanes/voz", {"voz_chalan": "Háblame de tú."})
    assert resp.status_code == 302
    u.refresh_from_db()
    assert u.voz_chalan == "Háblame de tú."


def test_post_voz_personal_vacia_limpia(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    u.voz_chalan = "algo viejo"
    u.save(update_fields=["voz_chalan"])
    client.force_login(u)
    resp = client.post("/perfil/chalanes/voz", {"voz_chalan": "   "})
    assert resp.status_code == 302
    u.refresh_from_db()
    assert u.voz_chalan == ""


def test_post_voz_personal_sanea(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/perfil/chalanes/voz", {"voz_chalan": "Hola <script>x</script> directo"})
    u.refresh_from_db()
    assert "<script>" not in u.voz_chalan
    assert "directo" in u.voz_chalan


def test_panel_muestra_voz_personal_actual(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    u.voz_chalan = "MI ESTILO PERSONAL"
    u.save(update_fields=["voz_chalan"])
    client.force_login(u)
    resp = client.get("/perfil/chalanes/")
    assert resp.status_code == 200
    assert "MI ESTILO PERSONAL" in resp.content.decode()
