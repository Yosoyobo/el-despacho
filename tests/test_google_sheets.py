"""Wrapper de Google Sheets (S-Drive-Cierre). No pega a Google: mockea la
creación del archivo y la escritura de valores."""

from __future__ import annotations


def test_crear_hoja_sin_drive_no_lanza(monkeypatch):
    import lib.google_sheets as gs
    from lib.google_drive import drive

    monkeypatch.setattr(drive, "esta_configurado", lambda: False)
    res = gs.crear_hoja(titulo="X", encabezados=["A"], filas=[["1"]], subcarpeta="Tesorería")
    assert res.ok is False
    assert "Drive" in res.error


def test_crear_hoja_ok(monkeypatch):
    import lib.google_sheets as gs
    from lib.google_drive import drive

    capturado = {}
    monkeypatch.setattr(drive, "esta_configurado", lambda: True)
    monkeypatch.setattr(drive, "obtener_o_crear_subcarpeta", lambda nombre: "CARP")
    monkeypatch.setattr(gs, "_crear_archivo_hoja", lambda titulo, carpeta_id: "SHEET1")

    def fake_escribir(sid, valores):
        capturado["sid"] = sid
        capturado["valores"] = valores

    monkeypatch.setattr(gs, "_escribir_valores", fake_escribir)

    res = gs.crear_hoja(
        titulo="Tesorería · egresos", encabezados=["Código", "Monto"],
        filas=[["EGR-1", "100.00"], ["EGR-2", "50.00"]], subcarpeta="Tesorería",
    )
    assert res.ok
    assert res.id == "SHEET1"
    assert res.url == "https://docs.google.com/spreadsheets/d/SHEET1"
    # Primera fila = encabezados; luego las filas.
    assert capturado["valores"][0] == ["Código", "Monto"]
    assert capturado["valores"][1] == ["EGR-1", "100.00"]


def test_crear_hoja_falla_envuelve_error(monkeypatch):
    import lib.google_sheets as gs
    from lib.google_drive import drive

    monkeypatch.setattr(drive, "esta_configurado", lambda: True)
    monkeypatch.setattr(drive, "obtener_o_crear_subcarpeta", lambda nombre: "CARP")
    monkeypatch.setattr(
        gs, "_crear_archivo_hoja",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("403 sin permiso")),
    )
    res = gs.crear_hoja(titulo="X", encabezados=["A"], filas=[], subcarpeta="Tesorería")
    assert res.ok is False
    assert "Sheets" in res.error
