"""D5 (LC 2026-07) — imagen de producto: subir/pegar a Drive."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _servicio():
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="C")
    return Servicio.objects.create(nombre="Playera", categoria=cat, precio_base=Decimal("100"), activo=True)


def test_subir_imagen_guarda_file_id(client, usuario_factory, monkeypatch):
    import lib.adjuntos as adj
    from django.core.files.uploadedfile import SimpleUploadedFile
    monkeypatch.setattr(
        adj, "subir",
        lambda archivo, subcarpeta=None: SimpleNamespace(
            ok=True, data={"id": "drive123", "webViewLink": "https://drive/view/123"}, error=""),
    )
    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    client.force_login(admin)
    img = SimpleUploadedFile("captura.png", b"\x89PNG\r\n\x1a\n fake", content_type="image/png")
    resp = client.post(f"/catalogo/{srv.pk}/imagen", {"imagen": img})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    srv.refresh_from_db()
    assert srv.imagen_file_id == "drive123"
    assert srv.imagen_url == "https://drive/view/123"


def test_subir_sin_imagen_400(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    client.force_login(admin)
    resp = client.post(f"/catalogo/{srv.pk}/imagen", {})
    assert resp.status_code == 400


def test_drive_falla_es_gracioso(client, usuario_factory, monkeypatch):
    import lib.adjuntos as adj
    from django.core.files.uploadedfile import SimpleUploadedFile
    monkeypatch.setattr(
        adj, "subir",
        lambda archivo, subcarpeta=None: SimpleNamespace(ok=False, data={}, error="Drive no conectado"),
    )
    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    client.force_login(admin)
    img = SimpleUploadedFile("x.png", b"fake", content_type="image/png")
    resp = client.post(f"/catalogo/{srv.pk}/imagen", {"imagen": img})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""  # no se guardó nada
