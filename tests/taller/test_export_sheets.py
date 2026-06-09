"""Export 'Crear hoja en Drive' de Tesorería (S-Drive-Cierre)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_crear_hoja_drive_usa_filas_para(monkeypatch, usuario_factory):
    from apps.tesoreria import exports

    from lib.google_sheets import ResultadoHoja

    capt = {}

    def fake_crear(*, titulo, encabezados, filas, subcarpeta=None):
        capt["titulo"] = titulo
        capt["encabezados"] = encabezados
        capt["subcarpeta"] = subcarpeta
        return ResultadoHoja(ok=True, id="S1", url="http://sheet/S1")

    monkeypatch.setattr("lib.google_sheets.crear_hoja", fake_crear)
    res, num = exports.crear_hoja_drive("ingresos", {})
    assert res.ok
    assert capt["subcarpeta"] == "Tesorería"
    assert "ingresos" in capt["titulo"]
    assert "Código" in capt["encabezados"]


def test_vista_export_sheets_redirige_a_la_hoja(client, usuario_factory, monkeypatch):
    from apps.tesoreria import exports

    from lib.google_sheets import ResultadoHoja

    monkeypatch.setattr(
        exports, "crear_hoja_drive",
        lambda vista, params: (ResultadoHoja(ok=True, id="S9", url="http://sheet/S9"), 3),
    )
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/tesoreria/exportar/egresos/hoja")
    assert resp.status_code == 302
    assert resp["Location"] == "http://sheet/S9"


def test_vista_export_sheets_sin_drive_degrada(client, usuario_factory):
    # Sin credenciales de Drive → crear_hoja devuelve ok=False → redirige a landing.
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/tesoreria/exportar/ingresos/hoja")
    assert resp.status_code == 302
    assert resp["Location"].endswith("/tesoreria/")


def test_vista_export_sheets_vista_invalida(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/tesoreria/exportar/inexistente/hoja")
    assert resp.status_code == 405
