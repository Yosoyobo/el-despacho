"""Wrapper HTML→PDF de Google Drive + helper lib.documentos (S-Drive-Cierre).

No pega a Google: mockea los métodos HTTP del wrapper. Verifica la
orquestación (html→Gdoc→export→sube PDF→borra Doc) y el fallback gracioso del
helper cuando Drive no está configurado.
"""

from __future__ import annotations

import pytest


def test_html_a_pdf_orquesta_y_borra_doc_temporal(monkeypatch):
    from lib.google_drive import GoogleDriveWrapper

    w = GoogleDriveWrapper()
    llamadas = {}

    def fake_subir_gdoc(html, nombre, carpeta_id):
        llamadas["gdoc"] = (html, nombre, carpeta_id)
        return "DOC123"

    def fake_exportar(file_id, mime_destino):
        llamadas["export"] = (file_id, mime_destino)
        return b"%PDF-fake"

    def fake_subir_contenido(contenido, nombre, carpeta_id, mime):
        llamadas["subir_pdf"] = (contenido, nombre, mime)
        return {"id": "PDF999", "name": nombre, "webViewLink": "http://x/PDF999"}

    def fake_borrar(file_id):
        llamadas["borrado"] = file_id

    monkeypatch.setattr(w, "_subir_html_como_gdoc", fake_subir_gdoc)
    monkeypatch.setattr(w, "exportar", fake_exportar)
    monkeypatch.setattr(w, "_subir_contenido", fake_subir_contenido)
    monkeypatch.setattr(w, "borrar", fake_borrar)

    meta = w.html_a_pdf(html="<h1>hola</h1>", nombre="COT-2026-0001", carpeta_id="CARP")

    assert meta["id"] == "PDF999"
    assert meta["pdf_bytes"] == b"%PDF-fake"
    assert llamadas["export"] == ("DOC123", "application/pdf")
    assert llamadas["borrado"] == "DOC123"          # el Doc temporal se limpia
    assert llamadas["subir_pdf"][1] == "COT-2026-0001.pdf"  # extensión añadida
    assert llamadas["subir_pdf"][2] == "application/pdf"


def test_html_a_pdf_borra_doc_aunque_falle_export(monkeypatch):
    from lib.google_drive import GoogleDriveWrapper

    w = GoogleDriveWrapper()
    borrados = []
    monkeypatch.setattr(w, "_subir_html_como_gdoc", lambda h, n, c: "DOCX")
    monkeypatch.setattr(w, "exportar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(w, "borrar", lambda fid: borrados.append(fid))

    with pytest.raises(RuntimeError):
        w.html_a_pdf(html="x", nombre="X")
    assert borrados == ["DOCX"]  # se limpió pese al error


def test_documentos_generar_pdf_sin_drive_no_lanza(monkeypatch):
    """Fallback gracioso: sin Drive configurado devuelve ok=False, no lanza."""
    import lib.documentos as doc
    from lib.google_drive import drive

    monkeypatch.setattr(drive, "esta_configurado", lambda: False)
    res = doc.generar_pdf(html="<p>x</p>", nombre="X", subcarpeta="Cotizaciones")
    assert res.ok is False
    assert "Drive" in res.error


def test_documentos_generar_pdf_ok(monkeypatch):
    import lib.documentos as doc
    from lib.google_drive import drive

    monkeypatch.setattr(drive, "esta_configurado", lambda: True)
    monkeypatch.setattr(drive, "obtener_o_crear_subcarpeta", lambda nombre: "CARP")
    # LC 2026-08-17: el doble acepta `pagina` (márgenes y pie del documento) y lo
    # CAPTURA. El fallback de `generar_pdf` atrapa cualquier excepción, así que un
    # doble con la firma vieja no fallaba con un `TypeError` legible: devolvía
    # `ok=False` y el test parecía un problema de Drive. Verificar que el
    # parámetro viaja convierte esa trampa en garantía.
    visto = {}

    def _falso(*, html, nombre, carpeta_id, pagina=None):
        visto["pagina"] = pagina
        return {"id": "P1", "webViewLink": "http://x/P1", "pdf_bytes": b"%PDF"}

    monkeypatch.setattr(drive, "html_a_pdf", _falso)
    res = doc.generar_pdf(html="<p>x</p>", nombre="X", subcarpeta="Cotizaciones",
                          pagina={"margen_superior_pt": 36})
    assert res.ok is True
    assert res.data["id"] == "P1"
    assert res.pdf_bytes == b"%PDF"
    assert visto["pagina"] == {"margen_superior_pt": 36}

    # Y sin `pagina` (las facturas) llega None: los márgenes de siempre.
    doc.generar_pdf(html="<p>x</p>", nombre="X", subcarpeta="Facturas")
    assert visto["pagina"] is None
