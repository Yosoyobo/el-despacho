"""S-LC-Feedback-V3: página de Ayuda con manual renderizado."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_ayuda_redirige_si_anonimo(client):
    resp = client.get("/ayuda/")
    assert resp.status_code in (301, 302)


def test_ayuda_renderiza_para_usuario(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ayuda/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # El manual debe contener algunas secciones esperadas.
    assert "manual" in body.lower() or "Despacho" in body
    # La tabla de contenidos debe renderizarse.
    assert "manual-toc" in body
    assert "manual-cuerpo" in body


def test_ayuda_raw_descarga_markdown(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ayuda/raw")
    assert resp.status_code == 200
    assert "text/markdown" in resp.get("Content-Type", "")
