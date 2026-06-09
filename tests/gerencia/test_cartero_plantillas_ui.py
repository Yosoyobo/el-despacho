"""UI del editor de plantillas de El Cartero (GrapesJS + IA). Solo super_admin."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_lista_plantillas(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/plantillas/")
    assert resp.status_code == 200
    assert "Cotización" in resp.content.decode()


def test_editar_get_carga_editor(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/plantillas/factura/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "grapesjs" in body  # el editor se carga
    assert "El Chalán" in body  # botón de IA


def test_editar_post_guarda(client, usuario_factory):
    from ajustes.models import PlantillaCorreo
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/plantillas/factura/", {
        "asunto": "Nueva factura {{ codigo }}",
        "cuerpo_html": "<p>Hola {{ cliente }}</p>",
    })
    assert resp.status_code == 302
    pl = PlantillaCorreo.obtener("factura")
    assert pl.asunto == "Nueva factura {{ codigo }}"
    assert "{{ cliente }}" in pl.cuerpo_html


def test_redactar_endpoint_json(client, usuario_factory, monkeypatch):
    from lib import cartero_ia
    monkeypatch.setattr(cartero_ia, "redactar",
                        lambda **kw: {"ok": True, "html": "<p>IA {{ codigo }}</p>", "error": ""})
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/plantillas/cotizacion/redactar",
                       {"intencion": "más formal", "html_actual": "<p>x</p>"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "{{ codigo }}" in data["html"]


def test_disenador_sin_acceso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/ajustes/cartero/plantillas/").status_code in (302, 403)
