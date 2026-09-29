"""La Imprenta (2026-09-29): los ajustes de los documentos PDF.

Oscar: «quiero poder editar, modificar y personalizar aún más la generación de
PDFs». Lo que se cuida aquí:

1. **De fábrica, el documento de siempre.** Quien no toca nada no ve ni un
   píxel distinto: los trozos de estilo con los defaults son los que la
   plantilla traía escritos a mano.
2. **La vista previa no guarda.** Un borrador se dibuja encima de lo guardado
   sin tocar la base.
3. **Google sale «básico».** Si Chromium se cae, Google arma el PDF con el
   formato de siempre, pero con el CONTENIDO elegido (rótulos, textos): eso es
   lo que el cliente acepta.
4. **Vacío hereda, cero es cero** en la hoja de cada tipo.
5. **Las fuentes viajan pegadas** a la conversión; el color de la marca no
   puede meter CSS.
6. **El historial**: foto inicial, resumen en palabras, restaurar, y el testigo
   que no deja pisar lo que guardó otra persona.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _sin_cache():
    from imprenta import config

    config.olvidar()
    yield
    config.olvidar()


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cot(cliente_factory, jefe):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    c = Cotizacion.objects.create(cliente=cliente_factory(creado_por=jefe, razon_social="Optimist"),
                                  titulo="Termos Optimist", creado_por=jefe,
                                  estado="generada")
    CotizacionItem.objects.create(cotizacion=c, orden=0, concepto="Termo",
                                  descripcion="Acero\n500 ml",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100"))
    CotizacionItem.objects.create(cotizacion=c, orden=1, concepto="Taza",
                                  cantidad=Decimal("5"), precio_unitario=Decimal("80"))
    return c


def _html(cot, **borrador):
    from apps.cotizaciones import services

    from imprenta import config

    cfg = config.resolver("cotizacion", borrador=borrador or None)
    return services.construir_html_pdf(cot, config=cfg)


# ── 1. De fábrica, el documento de siempre ──────────────────────────────────


def test_los_trozos_de_estilo_de_fabrica_son_los_de_siempre():
    from imprenta.config import resolver

    e = resolver("cotizacion").e
    assert e.td == "border:1px solid #cccccc; padding:1pt 5pt;"
    assert e.th == "border:1px solid #cccccc; padding:1pt 5pt; background-color:#f2f2f2;"
    assert e.th_letra == "font-style:italic;"
    assert e.titulo == "text-align:center;"
    assert e.total == ""
    assert e.fuentes_css == "", "con Arial no se pega ninguna fuente"
    assert "Arial" in e.cuerpo and "font-size: 11pt" in e.cuerpo
    assert e.logo_pt == e.logo_ancho == 50


def test_la_cotizacion_de_fabrica_sale_como_siempre(cot):
    html = _html(cot)
    assert "Logo_LC-256.png" in html
    assert 'width="50" height="50"' in html
    assert ">Concepto<" in html and ">P. Unitario<" in html
    assert "Notas:" in html
    assert "OPTIMIST" in html, "el cliente arriba a la derecha"
    assert "Acero" in html, "las especificaciones del concepto"


def test_el_interlineado_de_la_hoja_se_aplica(cot):
    """Antes la pantalla lo guardaba y la plantilla traía 1.02 escrito a mano."""
    from ajustes.models import ConfiguracionDocumento

    hoja = ConfiguracionDocumento.obtener()
    hoja.interlineado = Decimal("1.07")
    hoja.save()
    assert "line-height: 1.07;" in _html(cot)


# ── 2. El borrador (vista previa sin guardar) ───────────────────────────────


def test_el_borrador_cambia_el_documento_sin_guardar(cot):
    from imprenta.models import AjusteImprenta

    html = _html(cot, marca={"color_acento": "#d92d20", "fuente_cuerpo": "lato"},
                 cotizacion={"col_precio": "Precio c/u"})
    assert "color:#d92d20;" in html, "el total no tomó el color de acento"
    assert "@font-face{font-family:'LCLato'" in html
    assert "font-family: LCLato, Arial" in html.split("<body", 1)[1][:200], "el cuerpo no usa la letra elegida"
    assert ">Precio c/u<" in html and ">P. Unitario<" not in html
    assert not AjusteImprenta.objects.exists(), "la vista previa guardó algo"


def test_apagar_bloques_los_quita(cot):
    html = _html(cot, cotizacion={"bloque_notas": False, "bloque_montos": False,
                                  "bloque_descripcion": False, "bloque_cliente": False})
    assert "Notas:" not in html
    assert ">P. Unitario<" not in html
    assert "Acero" not in html
    assert "OPTIMIST" not in html


def test_los_datos_del_despacho_salen_si_el_tipo_los_pide(cot):
    despacho = {"rfc": "LCE010101AB1", "clabe": "012345678901234567", "banco": "BBVA"}
    assert "LCE010101AB1" not in _html(cot, despacho=despacho)
    html = _html(cot, despacho=despacho,
                 cotizacion={"datos_despacho": ["rfc", "bancarios"]})
    assert "LCE010101AB1" in html
    assert "CLABE: 012345678901234567" in html


def test_el_titulo_acepta_piezas(cot):
    html = _html(cot, cotizacion={"titulo": "Propuesta {folio} para {cliente}"})
    assert f"Propuesta {cot.codigo} para Optimist" in html


# ── 3. Google sale básico ───────────────────────────────────────────────────


def test_en_modo_basico_se_va_lo_visual_y_se_queda_el_contenido():
    from imprenta.config import resolver
    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="marca", valores={"fuente_cuerpo": "lato",
                                                           "color_acento": "#d92d20"})
    AjusteImprenta.objects.create(ambito="cotizacion", valores={"col_precio": "Precio c/u",
                                                                "texto_intro": "Hola"})
    cfg = resolver("cotizacion", basico=True)
    assert cfg.marca["fuente_cuerpo"] == "arial"
    assert cfg.marca["color_acento"] == "#000000"
    assert cfg.doc["col_precio"] == "Precio c/u", "un rótulo es contenido, no formato"
    assert cfg.doc["texto_intro"] == "Hola"


def test_generar_pdf_le_da_a_google_la_version_basica(cot, jefe, monkeypatch):
    from apps.cotizaciones import services

    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="marca", valores={"fuente_cuerpo": "lato"})
    capturado = {}

    class _Res:
        ok = False
        error = "sin Drive"

    def _falso(**kw):
        capturado.update(kw)
        return _Res()

    monkeypatch.setattr("lib.documentos.generar_pdf", _falso)
    services.generar_pdf(cot, jefe)
    assert "LCLato" in capturado["html"]
    assert "LCLato" not in capturado["html_google"](), "Google recibió la letra que no respeta"
    assert "Lato-Regular.ttf" in capturado["pagina"]["fuentes"]


def test_el_generador_usa_la_version_de_google_solo_si_va_por_google(monkeypatch):
    from lib import documentos, gotenberg

    llamado = {"google": 0}

    def _html_google():
        llamado["google"] += 1
        return "<p>basico</p>"

    class _Drive:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, n):
            return "c"

        def _subir_contenido(self, *a):
            return {"id": "x"}

        def html_a_pdf(self, html, nombre, carpeta_id=None, pagina=None):
            llamado["html"] = html
            llamado["pagina"] = pagina
            return {"id": "g", "pdf_bytes": b"%PDF"}

    import lib.google_drive as gd
    monkeypatch.setattr(gd, "drive", _Drive(), raising=False)
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF")
    documentos.olvidar_configuracion()
    res = documentos.generar_pdf(html="<p>lleno</p>", nombre="d", html_google=_html_google,
                                 pagina={"fuentes": ["Lato-Regular.ttf"]})
    assert res.motor == "gotenberg" and llamado["google"] == 0

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    res = documentos.generar_pdf(html="<p>lleno</p>", nombre="d", html_google=_html_google,
                                 pagina={"fuentes": ["Lato-Regular.ttf"]})
    assert res.motor == "google"
    assert llamado["html"] == "<p>basico</p>"
    assert "fuentes" not in llamado["pagina"], "a Google no le sirven las fuentes pegadas"


# ── 4. Vacío hereda, cero es cero ───────────────────────────────────────────


def test_la_hoja_de_un_tipo_hereda_lo_vacio_y_respeta_el_cero():
    from imprenta.config import pagina, resolver

    base = pagina(resolver("cotizacion"))
    assert base["margen_superior_pt"] == 36

    cfg = resolver("cotizacion", borrador={"cotizacion": {
        "margen_superior_pt": None, "margen_izquierdo_pt": 0, "tamano_papel": "oficio"}})
    pag = pagina(cfg)
    assert pag["margen_superior_pt"] == 36, "un margen vacío no heredó el de la hoja general"
    assert pag["margen_izquierdo_pt"] == 0, "un cero escrito se tomó como «sin valor»"
    assert pag["alto_in"] == 13.0


def test_el_campo_entero_opcional_guarda_none_y_no_cero():
    from imprenta import esquema

    campo = next(c for c in esquema.campos_hoja() if c.clave == "margen_superior_pt")
    assert campo.limpiar("") is None
    assert campo.limpiar("0") == 0
    assert campo.limpiar("9999") == 216


def test_el_estimador_sigue_a_la_hoja_del_tipo():
    """Con la hoja de fábrica, el alto útil del estimador no se mueve ni un punto;
    con oficio (13 pulgadas contra 11) crece lo que crece la hoja: 144pt."""
    from apps.cotizaciones import services

    from imprenta.config import resolver

    assert services._alto_util_de(resolver("cotizacion")) == services._ALTO_UTIL_PT
    oficio = resolver("cotizacion", borrador={"cotizacion": {"tamano_papel": "oficio"}})
    assert services._alto_util_de(oficio) == services._ALTO_UTIL_PT + 144


# ── 5. Lo que viaja al motor ────────────────────────────────────────────────


def test_las_fuentes_viajan_pegadas_a_la_conversion(monkeypatch):
    from lib import gotenberg

    enviado = {}

    def _postear(ruta, campos, partes):
        enviado["campos"], enviado["partes"] = campos, partes
        return b"%PDF"

    monkeypatch.setattr(gotenberg, "_postear", _postear)
    gotenberg.html_a_pdf("<html><body>x</body></html>",
                         pagina={"fuentes": ["Lato-Regular.ttf", "../../../../lib/gotenberg.py"],
                                 "pdfa": True})
    nombres = [p[1] for p in enviado["partes"]]
    assert "Lato-Regular.ttf" in nombres
    # La ruta con ../ apunta a un archivo que SÍ existe fuera del directorio de
    # las fuentes: si se siguiera, viajaría código del servidor a la conversión.
    assert not any("gotenberg" in n for n in nombres), "una ruta con ../ salió del directorio"
    assert enviado["campos"]["pdfa"] == "PDF/A-2b"


def test_el_color_de_la_marca_de_agua_no_mete_css():
    from lib import gotenberg

    css = gotenberg._marca_agua_css("BORRADOR", "red;} body{display:none")
    assert "display:none" not in css
    assert "#d92d20" in css
    assert "#12b76a" in gotenberg._marca_agua_css("PAGADA", "#12b76a")


def test_todas_las_fuentes_del_esquema_existen():
    """Una fuente declarada sin su archivo saldría con la letra de respaldo en
    silencio."""
    from imprenta import esquema
    from lib import gotenberg

    for clave, (_, _, archivos) in esquema.FUENTES.items():
        for archivo in archivos.values():
            assert (gotenberg.DIR_FUENTES / archivo).is_file(), f"{clave}: falta {archivo}"


# ── 6. Historial, restaurar y el testigo ────────────────────────────────────


def test_guardar_toma_la_foto_inicial_y_resume_en_palabras(jefe):
    from imprenta import servicios
    from imprenta.models import VersionImprenta

    v = servicios.guardar({"marca": {"fuente_cuerpo": "lato"}}, jefe, motivo="Marca")
    inicial = VersionImprenta.objects.order_by("pk").first()
    assert inicial.motivo == "Estado inicial" and inicial.pk != v.pk
    assert any("Letra del documento: Arial (la de siempre) → Lato" in r for r in v.resumen)


def test_restaurar_vuelve_y_queda_anotado(jefe):
    from imprenta import config, servicios
    from imprenta.models import VersionImprenta

    servicios.guardar({"marca": {"color_acento": "#d92d20"}, "hoja": {"motor": "google"}}, jefe)
    inicial = VersionImprenta.objects.order_by("pk").first()
    nueva = servicios.restaurar(inicial, jefe)
    assert nueva.restaurada_de_id == inicial.pk
    cfg = config.resolver("cotizacion")
    assert cfg.marca["color_acento"] == "#000000"
    assert cfg.hoja.motor == "auto"


def test_el_testigo_no_deja_pisar_lo_que_guardo_otra_persona(jefe, usuario_factory):
    from imprenta import servicios

    otra = usuario_factory(rol="super_admin")
    base = servicios.guardar({"marca": {"color_acento": "#111111"}}, jefe).pk
    servicios.guardar({"marca": {"color_acento": "#222222"}}, otra)   # alguien guarda encima

    choque = servicios.revisar_choque(base, {"marca": {"color_acento": "#333333"}})
    assert choque is not None and any("Color de acento" in c for c in choque.campos)

    # Tocar OTRO campo no choca con nada.
    assert servicios.revisar_choque(base, {"marca": {"color_acento": "#222222",
                                                     "fuente_cuerpo": "lato"}}) is None


def test_el_testigo_desde_antes_del_historial(jefe, usuario_factory):
    """Se abrió la pantalla sin historial (base=0) y alguien guardó después."""
    from imprenta import servicios

    servicios.guardar({"marca": {"color_acento": "#222222"}}, usuario_factory(rol="super_admin"))
    assert servicios.revisar_choque(0, {"marca": {"color_acento": "#333333"}}) is not None
    assert servicios.revisar_choque(None, {"marca": {"color_acento": "#333333"}}) is None


# ── 7. El Chalán y el MCP ───────────────────────────────────────────────────


def test_el_chalan_lee_el_formato_con_la_clabe_enmascarada(jefe):
    import capacidades
    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="despacho", valores={"clabe": "012345678901234567"})
    AjusteImprenta.objects.create(ambito="cotizacion", valores={"bloque_fotos": False,
                                                                "col_precio": "Precio c/u"})
    res = capacidades.ejecutar("formato_documentos", {}, jefe)
    texto = str(res)
    assert "012345678901234567" not in texto, "la CLABE completa salió por el chat"
    assert "…4567" in texto
    assert "Foto de cada concepto" in texto and "Precio c/u" in texto


def test_el_formato_de_documentos_pide_su_permiso(usuario_factory):
    import capacidades

    miembro = usuario_factory(rol="miembro")
    assert "formato_documentos" not in {c.nombre for c in capacidades.listar(miembro)}


def test_el_servidor_mcp_expone_el_formato():
    from mcp_despacho import herramientas, servidor

    assert callable(getattr(herramientas, "formato_documentos", None))
    assert callable(getattr(servidor, "formato_documentos", None))
