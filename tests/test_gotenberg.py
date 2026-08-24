"""Gotenberg — el motor de PDF que corre en el NUC (S-NUC-Servicios).

Lo que estas pruebas cuidan, en orden de lo que dolería si se rompe:

1. Que **el fallback funcione**. Si el servicio no contesta, los documentos
   tienen que seguir saliendo por Google. Un despacho que no puede mandar una
   cotización porque un contenedor se cayó es peor que uno con PDFs feos.
2. Que el pie lleve **numeración real**. Es la razón principal del cambio: la
   API de Google no podía, y el pie decía «1/1» en documentos de tres hojas.
3. Que los **márgenes se traduzcan** de puntos a pulgadas. El repo entero habla
   en puntos (`PAGINA_DOCUMENTO`) y Chromium en pulgadas; equivocar el factor
   daría márgenes 72 veces más grandes, o sea una hoja en blanco.
4. Que **no se sondee el servicio en cada PDF**.
"""

from __future__ import annotations

import pytest

from lib import documentos, gotenberg


@pytest.fixture(autouse=True)
def _sin_cache():
    """El veredicto de salud vive en el módulo: sin esto, una prueba le
    heredaría a la siguiente lo que decidió."""
    gotenberg.olvidar_salud()
    yield
    gotenberg.olvidar_salud()


# ── El pie, que es el motivo del cambio ────────────────────────────────────


def test_el_pie_numera_paginas_de_verdad():
    """`pageNumber` y `totalPages` los sustituye Chromium al imprimir. Es lo
    que la API de Documentos NO podía hacer, y por eso el pie decía «1/1»."""
    html = gotenberg._pie_html("Learning Center")
    assert "pageNumber" in html
    assert "totalPages" in html
    assert "Learning Center" in html


def test_el_pie_trae_su_propio_tamano_de_letra():
    """Chromium no hereda los estilos del documento en el pie: sin un
    `font-size` propio saldría enorme."""
    assert "font-size" in gotenberg._pie_html("x")


# ── Márgenes: puntos a pulgadas ────────────────────────────────────────────


def test_los_margenes_se_traducen_de_puntos_a_pulgadas():
    """72 puntos son una pulgada. Equivocar el factor daría márgenes 72 veces
    más grandes: una hoja en blanco."""
    assert gotenberg._pt_a_pulgadas(72, 1.0) == 1.0
    assert gotenberg._pt_a_pulgadas(36, 1.0) == 0.5


def test_un_margen_ausente_o_basura_cae_al_default():
    assert gotenberg._pt_a_pulgadas(None, 1.0) == 1.0
    assert gotenberg._pt_a_pulgadas("ancho", 1.0) == 1.0


def test_el_cuerpo_lleva_el_html_los_margenes_y_el_pie(monkeypatch):
    enviado = {}

    class _Resp:
        status = 200

        def read(self):
            return b"%PDF-1.4 fake"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _falso_urlopen(req, timeout=None):
        enviado["cuerpo"] = req.data
        enviado["url"] = req.full_url
        return _Resp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _falso_urlopen)

    pdf = gotenberg.html_a_pdf(
        "<h1>Cotización</h1>",
        pagina={"margen_superior_pt": 36, "pie_texto": "Learning Center"},
    )

    assert pdf == b"%PDF-1.4 fake"
    cuerpo = enviado["cuerpo"].decode("utf-8", "replace")
    assert "convert/html" in enviado["url"]
    assert "<h1>Cotización</h1>" in cuerpo
    assert 'filename="index.html"' in cuerpo
    assert 'filename="footer.html"' in cuerpo
    assert "0.5" in cuerpo, "el margen superior de 36pt debía viajar como media pulgada"
    assert "printBackground" in cuerpo, "sin esto los encabezados salen sin sombreado"


def test_un_5xx_del_servicio_se_reporta(monkeypatch):
    """Aquí sí se lanza: quien llama tiene el try que decide caer a Google.
    Tragárselo dejaría pasar un PDF vacío por bueno."""

    class _Resp:
        status = 503

        def read(self):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError):
        gotenberg.html_a_pdf("<p>x</p>")


# ── Salud y caché ──────────────────────────────────────────────────────────


def test_no_se_sondea_el_servicio_en_cada_pdf(monkeypatch):
    llamadas = {"n": 0}

    def _contar():
        llamadas["n"] += 1
        return True

    monkeypatch.setattr(gotenberg, "_sondear", _contar)
    for _ in range(5):
        gotenberg.disponible()
    assert llamadas["n"] == 1


def test_servicio_caido_no_lanza(monkeypatch):
    import urllib.request

    def _explota(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _explota)
    assert gotenberg.disponible(forzar=True) is False


# ── La integración: quién arma el documento ────────────────────────────────


def test_si_gotenberg_no_esta_los_documentos_salen_por_google(monkeypatch):
    """El fallback es lo que evita que un contenedor caído impida mandar una
    cotización."""
    monkeypatch.setattr(gotenberg, "disponible", lambda: False)

    llamado = {"google": False}

    class _DriveFalso:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, nombre):
            return "carpeta"

        def html_a_pdf(self, html, nombre, carpeta_id=None, pagina=None):
            llamado["google"] = True
            return {"id": "abc", "pdf_bytes": b"%PDF google"}

    _parchar_drive(monkeypatch, _DriveFalso())
    res = documentos.generar_pdf(html="<p>x</p>", nombre="doc")
    assert res.ok and res.motor == "google"
    assert llamado["google"], "no se usó el camino de Google"


def test_si_gotenberg_esta_se_usa_y_google_no_convierte(monkeypatch):
    monkeypatch.setattr(gotenberg, "disponible", lambda: True)
    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF chromium")

    llamado = {"google": False}

    class _DriveFalso:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, nombre):
            return "carpeta"

        def html_a_pdf(self, **k):
            llamado["google"] = True
            return {}

        def _subir_contenido(self, contenido, nombre, carpeta_id, mime):
            assert mime == "application/pdf"
            assert nombre.endswith(".pdf"), "el nombre debe llevar extensión"
            return {"id": "xyz", "webViewLink": "http://drive/xyz"}

    _parchar_drive(monkeypatch, _DriveFalso())
    res = documentos.generar_pdf(html="<p>x</p>", nombre="doc", subcarpeta="Cotizaciones")
    assert res.ok and res.motor == "gotenberg"
    assert res.pdf_bytes == b"%PDF chromium"
    assert res.data["id"] == "xyz"
    assert not llamado["google"], "Google no debía convertir nada"


def test_si_gotenberg_falla_se_intenta_con_google(monkeypatch):
    monkeypatch.setattr(gotenberg, "disponible", lambda: True)

    def _explota(html, pagina=None):
        raise RuntimeError("chromium se murió")

    monkeypatch.setattr(gotenberg, "html_a_pdf", _explota)

    class _DriveFalso:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, nombre):
            return "carpeta"

        def html_a_pdf(self, html, nombre, carpeta_id=None, pagina=None):
            return {"id": "abc", "pdf_bytes": b"%PDF google"}

    _parchar_drive(monkeypatch, _DriveFalso())
    res = documentos.generar_pdf(html="<p>x</p>", nombre="doc")
    assert res.ok and res.motor == "google"


def test_si_drive_falla_el_pdf_generado_no_se_tira(monkeypatch):
    """El documento existe aunque no haya dónde guardarlo: devolverlo permite
    que el caller lo entregue de todos modos."""
    monkeypatch.setattr(gotenberg, "disponible", lambda: True)
    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF chromium")

    class _DriveFalso:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, nombre):
            raise RuntimeError("drive caído")

    _parchar_drive(monkeypatch, _DriveFalso())
    res = documentos.generar_pdf(html="<p>x</p>", nombre="doc", subcarpeta="Cotizaciones")
    assert res.ok is False
    assert res.pdf_bytes == b"%PDF chromium", "se perdió un PDF que sí se generó"
    assert "Drive" in res.error


def _parchar_drive(monkeypatch, falso):
    """`lib.documentos` importa `drive` DENTRO de la función, así que hay que
    parchear el módulo de origen y no un nombre ya importado."""
    import lib.google_drive as gd

    monkeypatch.setattr(gd, "drive", falso, raising=False)


# ── Las capacidades que Oscar pidió «supercharge» ──────────────────────────


def test_la_marca_de_agua_se_repite_en_todas_las_hojas():
    """`position: fixed` en modo impresión hace que Chromium la pinte en cada
    página. Se hace con CSS y no con un módulo del servicio para no depender de
    que Gotenberg traiga la capacidad."""
    css = gotenberg._marca_agua_css("BORRADOR")
    assert "position: fixed" in css
    assert "BORRADOR" in css


def test_la_marca_va_detras_del_contenido():
    """Una marca que tapa lo que hay debajo estorba en vez de avisar."""
    css = gotenberg._marca_agua_css("BORRADOR")
    assert "z-index: -1" in css
    assert "pointer-events: none" in css


def test_la_marca_no_deja_meter_etiquetas():
    """El texto lo escribe un humano en un formulario."""
    css = gotenberg._marca_agua_css("<script>alert(1)</script>")
    assert "<script>" not in css
    assert "&lt;script&gt;" in css


def test_sin_marca_no_se_inyecta_nada():
    assert gotenberg._marca_agua_css("") == ""
    assert gotenberg._inyectar("<html><body>x</body></html>", "") == "<html><body>x</body></html>"


def test_la_marca_entra_despues_del_body():
    r = gotenberg._inyectar("<html><body class='a'>hola</body></html>", "<i>M</i>")
    assert r == "<html><body class='a'><i>M</i>hola</body></html>"


def test_un_html_sin_body_tambien_recibe_la_marca():
    r = gotenberg._inyectar("<p>suelto</p>", "<i>M</i>")
    assert r.startswith("<i>M</i>")


def test_unir_pide_al_menos_dos():
    with pytest.raises(ValueError):
        gotenberg.unir([b"%PDF uno"])


def test_unir_manda_los_pdfs_en_orden(monkeypatch):
    """El orden importa: la cotización va primero y los anexos detrás."""
    visto = {}

    def _falso(ruta, campos, partes):
        visto["ruta"] = ruta
        visto["nombres"] = [p[1] for p in partes]
        return b"%PDF unido"

    monkeypatch.setattr(gotenberg, "_postear", _falso)
    r = gotenberg.unir([b"%PDF a", b"%PDF b", b"%PDF c"])
    assert r == b"%PDF unido"
    assert "merge" in visto["ruta"]
    assert visto["nombres"] == ["000.pdf", "001.pdf", "002.pdf"]


def test_unir_ignora_los_vacios(monkeypatch):
    monkeypatch.setattr(gotenberg, "_postear", lambda r, c, p: b"%PDF")
    gotenberg.unir([b"%PDF a", b"", b"%PDF b"])  # no debe lanzar


def test_reconoce_lo_que_es_de_office():
    assert gotenberg.es_office("cotizacion.docx")
    assert gotenberg.es_office("PRECIOS.XLSX"), "la extensión no distingue mayúsculas"
    assert not gotenberg.es_office("factura.pdf")
    assert not gotenberg.es_office("foto.jpg")


def test_convertir_algo_que_no_es_office_se_rechaza():
    with pytest.raises(ValueError):
        gotenberg.office_a_pdf(b"%PDF ya soy pdf", "factura.pdf")


def test_convertir_office_va_a_libreoffice(monkeypatch):
    visto = {}

    def _falso(ruta, campos, partes):
        visto["ruta"] = ruta
        visto["nombre"] = partes[0][1]
        return b"%PDF convertido"

    monkeypatch.setattr(gotenberg, "_postear", _falso)
    r = gotenberg.office_a_pdf(b"PK\x03\x04 docx", "propuesta.docx")
    assert r == b"%PDF convertido"
    assert "libreoffice" in visto["ruta"]
    assert visto["nombre"] == "propuesta.docx"


def test_el_encabezado_y_los_metadatos_viajan(monkeypatch):
    visto = {}

    def _falso(ruta, campos, partes):
        visto["campos"] = campos
        visto["archivos"] = [p[1] for p in partes]
        return b"%PDF"

    monkeypatch.setattr(gotenberg, "_postear", _falso)
    gotenberg.html_a_pdf("<p>x</p>", pagina={
        "encabezado_texto": "Learning Center",
        "metadatos": {"Title": "Cotización LC-0044", "Author": "Learning Center"},
    })
    assert "header.html" in visto["archivos"]
    assert "Cotización LC-0044" in visto["campos"]["metadata"]


def test_el_tamano_de_hoja_sale_del_ajuste(monkeypatch):
    """Sin esto, cambiar a oficio en el GUI no haría nada."""
    visto = {}
    monkeypatch.setattr(gotenberg, "_postear",
                        lambda r, c, p: visto.update(c) or b"%PDF")
    gotenberg.html_a_pdf("<p>x</p>", pagina={"ancho_in": 8.5, "alto_in": 13.0})
    assert visto["paperHeight"] == "13.0"
