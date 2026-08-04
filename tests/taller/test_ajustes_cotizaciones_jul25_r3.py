"""Tercera ronda de ajustes de Oscar sobre el deploy 2026.07.30.

Cubre lo que reportó:

1. **Los centavos de las facturas.** El total del despacho salía un centavo
   arriba del CFDI en toda base con centavo impar. La cuenta buena (Anexo 20:
   cada impuesto con su tasa nominal, redondeado por separado) ya vivía en
   `lib.fiscal`; lo que estaba mal era el preview del formulario, alimentado con
   los campos ⅔ deprecados. Aquí se blindan las 13 facturas reales que mandó.
2. **Régimen «IVA y Retenciones» por default**, incluido lo que crea El Chalán.
3. **El documento**: tabla de conceptos con línea negra delgada (y nada más),
   fecha/cliente al ras del logo, y el hueco de las notas con colchón al pie
   para que el último renglón no se vaya a otra hoja.
4. **Título del documento** en la columna principal, con el texto real cargado.
5. El botón del Dashboard ahora dice «Resumir pendientes».
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# Facturas reales de Learning Center: (folio, base, total del CFDI). El monto
# del CFDI es la verdad; el despacho tiene que dar exactamente eso.
FACTURAS_REALES = [
    ("F106", "2250", "2341.87"),
    ("F107", "14090", "14665.33"),
    ("F108", "22205", "23111.70"),
    ("F109", "61750", "64271.43"),
    ("F110", "6800", "7077.66"),
    ("F112", "20700", "21545.24"),
    ("F116", "2500", "2602.08"),
    ("F117", "26000", "27061.66"),
    ("F118", "3800", "3955.17"),
    ("F119", "17450", "18162.53"),
    ("F120", "11625", "12099.69"),
    ("F124", "570", "593.27"),
    ("F134", "27340", "28456.37"),
]


@pytest.fixture
def entorno(usuario_factory, cliente_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="Optimist",
                          razon_social_fiscal="MARKETING VEINTITRES GRADOS")
    proy = proyecto_factory(nombre="Marriott Bonvoy", cliente=cli, creado_por=admin)
    return {"admin": admin, "cli": cli, "proy": proy}


# ── 1. Los centavos ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(("folio", "base", "total_cfdi"), FACTURAS_REALES)
def test_total_honorarios_calza_con_el_cfdi(folio, base, total_cfdi):
    """Cada impuesto con su tasa NOMINAL y redondeado por separado (Anexo 20).

    La cuenta vieja (retención de IVA = ⅔ del IVA, redondeando solo al final)
    daba un centavo más en 9 de estas 13 facturas.
    """
    from lib.fiscal import desglose_honorarios

    d = desglose_honorarios(Decimal(base))
    assert str(d["total"]) == total_cfdi, folio


def test_factura_en_honorarios_da_el_total_del_cfdi(entorno):
    """El total que muestra la factura (backend) es el del CFDI, no el de ⅔."""
    from apps.facturacion.models import Factura, FacturaItem

    fac = Factura.objects.create(
        cliente=entorno["cli"], concepto="Bordado de mandiles",
        regimen_fiscal="honorarios", creado_por=entorno["admin"])
    FacturaItem.objects.create(
        factura=fac, descripcion="Bordado de mandiles",
        cantidad=1, precio_unitario=Decimal("2250"))
    assert str(fac.calcular_totales()["total"]) == "2341.87"


def test_preview_del_form_usa_la_tasa_nominal_no_la_fraccion(entorno, client):
    """El JS del preview recibe las TRES tasas nominales.

    Mientras la vista le pasó `ret_iva_num/den` (⅔ del IVA, campos deprecados),
    el preview quedaba un centavo arriba del total real.
    """
    client.force_login(entorno["admin"])
    body = client.get("/facturacion/nueva/").content.decode()
    assert 'data-ret-iva="10.6667"' in body
    assert "data-ret-iva-num" not in body
    assert "data-ret-iva-den" not in body


def test_fijar_total_con_impuestos_despeja_la_base_del_cfdi(entorno):
    """Dictar el importe final deja la factura con ese total exacto."""
    from apps.facturacion.models import Factura
    from apps.facturacion.services import fijar_total_con_impuestos

    fac = Factura.objects.create(
        cliente=entorno["cli"], concepto="Bordado de mandiles",
        regimen_fiscal="honorarios", creado_por=entorno["admin"])
    fijar_total_con_impuestos(fac, Decimal("2341.87"))
    assert str(fac.calcular_totales()["total"]) == "2341.87"


# ── 2. Régimen default + El Chalán ───────────────────────────────────────────

def test_documentos_nuevos_nacen_en_iva_y_retenciones(entorno):
    """Proyecto, cotización y factura nuevos: «IVA y Retenciones» (Oscar)."""
    from apps.cotizaciones.models import Cotizacion
    from apps.facturacion.models import Factura
    from apps.los_proyectos.models import Proyecto

    assert Proyecto().regimen_fiscal == "honorarios"
    assert Cotizacion().regimen_fiscal == "honorarios"
    assert Factura().regimen_fiscal == "honorarios"


class _Accion:
    """Lo mínimo que el ejecutor toca de una `DictadoAccion` (patrón del repo)."""

    def __init__(self, payload):
        self.payload = payload
        self.entidad_tipo = ""
        self.entidad_id = None


def _dictar_factura(payload, usuario):
    """Corre el ejecutor `crear_factura` como lo haría un dictado aplicado."""
    from apps.el_dictado.ejecutores.avanzados import crear_factura

    accion = _Accion(payload)
    crear_factura(accion, usuario)
    return accion


def test_chalan_una_sola_cifra_es_el_importe_final(entorno):
    """«Registra la factura de $2,341.87» ⇒ ése es el TOTAL, no la base."""
    from apps.facturacion.models import Factura

    accion = _dictar_factura({
        "cliente_slug": "optimist",
        "concepto": "Bordado de mandiles",
        "monto": "2341.87",
    }, entorno["admin"])
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert fac.regimen_fiscal == "honorarios"
    assert str(fac.calcular_totales()["total"]) == "2341.87"


def test_chalan_monto_base_le_suma_los_impuestos_encima(entorno):
    """«20,700 + IVA» ⇒ es el subtotal; el total sube con impuestos."""
    from apps.facturacion.models import Factura

    accion = _dictar_factura({
        "cliente_slug": "optimist",
        "concepto": "Producción",
        "monto_base": "20700",
    }, entorno["admin"])
    fac = Factura.objects.get(pk=accion.entidad_id)
    totales = fac.calcular_totales()
    assert str(totales["base_impuestos"]) == "20700.00"
    assert str(totales["total"]) == "21545.24"


def test_chalan_hereda_el_regimen_del_proyecto(entorno):
    """Si el proyecto está en «Exento», la factura dictada no lleva impuestos."""
    from apps.facturacion.models import Factura

    proy = entorno["proy"]
    proy.regimen_fiscal = "exento"
    proy.save(update_fields=["regimen_fiscal"])
    accion = _dictar_factura({
        "cliente_slug": "optimist",
        "proyecto_slug": proy.slug,
        "concepto": "Producción",
        "monto_base": "1000",
    }, entorno["admin"])
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert fac.regimen_fiscal == "exento"
    assert str(fac.calcular_totales()["total"]) == "1000.00"


def test_prompt_y_catalogo_declaran_la_regla_del_monto():
    """La regla vive en los tres lugares del contrato del Chalán."""
    from apps.el_dictado.prompt import SYSTEM_PROMPT

    from lib.dictado_catalogo import COMANDOS_DICTADO

    assert "IVA y Retenciones" in SYSTEM_PROMPT
    assert "importe FINAL de pago" in SYSTEM_PROMPT
    payload = next(c["payload"] for c in COMANDOS_DICTADO if c["tipo"] == "crear_factura")
    assert "monto_base" in payload and "FINAL" in payload


# ── 3. El documento ──────────────────────────────────────────────────────────

@pytest.fixture
def cotizacion(entorno):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    cot = Cotizacion.objects.create(
        cliente=entorno["cli"], proyecto=entorno["proy"], titulo="Ted Lasso",
        version=1, fecha_emision=date(2026, 7, 9), creado_por=entorno["admin"])
    CotizacionItem.objects.create(
        cotizacion=cot, concepto="Bufandas",
        descripcion="Bufanda fabricada desde cero\nSeda 100%",
        cantidad=100, precio_unitario=Decimal("395"))
    return cot


def test_tabla_de_conceptos_lleva_linea_gris_delgada(cotizacion):
    """Las tablas de conceptos llevan línea gris clara (Oscar 2026-07-26: «no
    negro»); el resto del documento sigue sin líneas."""
    from apps.cotizaciones.services import construir_html_pdf

    html = construir_html_pdf(cotizacion)
    assert "border:1px solid #000000" not in html
    assert html.count("border:1px solid #cccccc") >= 8  # 4 encabezados + 4 celdas
    # El encabezado (fecha/logo/cliente), los totales y las notas van sin líneas.
    encabezado = html.split("Bufandas")[0]
    assert "border:1px solid" not in encabezado
    assert "Notas:" in html


def test_tabla_del_desglose_tambien_lleva_recuadro(cotizacion):
    """Oscar 2026-07-25 (tercera ronda): «tabla desglose sí recuadro»."""
    from apps.cotizaciones.models import CotizacionItem
    from apps.cotizaciones.services import construir_html_pdf
    cotizacion.incluir_desglose = True
    cotizacion.save(update_fields=["incluir_desglose"])
    # LC 2026-08-04: con un solo producto la tabla del desglose ya no se imprime.
    CotizacionItem.objects.create(
        cotizacion=cotizacion, orden=1, concepto="Gorras",
        descripcion="50 pz", cantidad=50, precio_unitario=Decimal("120"))
    desglose = construir_html_pdf(cotizacion).split("Desglose de Elementos", 1)[1]
    tabla = desglose.split("</table>", 1)[0]
    assert tabla.count("border:1px solid #cccccc") >= 10  # 5 encabezados + 5 celdas
    assert "#999999" not in tabla  # la casilla ✔ va con la misma línea que el resto


def test_tablas_de_conceptos_centrada_y_sin_thead(cotizacion):
    """Docs mete un renglón en blanco entre `<thead>` y `<tbody>` (van sin esas
    etiquetas) y tampoco centra tablas: el centrado se logra con una columna
    vacía a cada lado dentro de la misma tabla (Oscar 2026-07-26)."""
    from apps.cotizaciones.services import construir_html_pdf

    cotizacion.incluir_desglose = True
    cotizacion.save(update_fields=["incluir_desglose"])
    html = construir_html_pdf(cotizacion)
    assert 'style="border:none; width:11%;"' in html
    assert "<thead>" not in html
    assert "<tbody>" not in html


def test_fecha_y_cliente_al_ras_del_logotipo(cotizacion):
    """El encabezado se lee como una sola línea, no centrado con el logo."""
    from apps.cotizaciones.services import construir_html_pdf

    html = construir_html_pdf(cotizacion)
    encabezado = html.split("Bufandas")[0]
    assert "vertical-align:middle" not in encabezado


def test_hueco_de_notas_deja_colchon_al_pie(cotizacion):
    """El bloque de notas nunca se pega al borde: si la estimación se pasa
    unos milímetros, el último renglón se iba a una hoja nueva."""
    from apps.cotizaciones.notas import notas_para
    from apps.cotizaciones.services import (
        _ALTO_UTIL_PT,
        _MARGEN_SEGURIDAD_PT,
        _espacio_antes_de_notas,
    )

    items = list(cotizacion.items.all())
    filas = [{"it": it, "imagen": "", "img_alto": 0} for it in items]
    notas = notas_para(cotizacion)
    hueco = _espacio_antes_de_notas(cotizacion, filas, items, notas)
    alto_notas = 22 + len(notas) * 15
    assert 0 < hueco <= _ALTO_UTIL_PT // 2
    assert hueco + alto_notas + _MARGEN_SEGURIDAD_PT <= _ALTO_UTIL_PT


def test_foto_apaisada_no_infla_la_estimacion(cotizacion):
    """Una foto banner (4:1) ocupa menos alto que una cuadrada, así que deja más
    hoja libre. LC 2026-07-26: el alto ya viene calculado en la fila (`img_alto`,
    de `_medida_foto`), no se deduce aquí de la proporción.

    LC 2026-07-29: se mide contra `_paginar` (la señal cruda) porque el hueco de
    las notas lleva tope y con un documento de una línea los dos casos saturan.
    """
    from apps.cotizaciones.services import _medida_foto, _paginar

    items = list(cotizacion.items.all())
    apaisada = [{"it": it, "imagen": "u", "img_alto": _medida_foto(0.25)[1]} for it in items]
    sin_medida = [{"it": it, "imagen": "u", "img_alto": _medida_foto(0)[1]} for it in items]
    assert (_paginar(cotizacion, apaisada, items)["libre"]
            > _paginar(cotizacion, sin_medida, items)["libre"])


def test_proporcion_sin_cache_no_lanza():
    """`proporcion` sólo lee de caché: sin imagen precalentada devuelve 0.0."""
    from lib.imagen_publica import proporcion

    assert proporcion("") == 0.0
    assert proporcion("no-existe-en-cache") == 0.0


# ── 4. Título del documento en la columna principal ──────────────────────────

def test_titulo_del_documento_viene_precargado_en_la_columna_principal(
        cotizacion, entorno, client):
    """Con placeholder había que reescribirlo: ahora trae el texto real."""
    client.force_login(entorno["admin"])
    body = client.get(f"/cotizaciones/{cotizacion.pk}/").content.decode()
    # Django escapa el apóstrofe del nombre, así que se busca el texto base.
    assert "Producción de elementos para proyecto" in body
    assert 'id="titulo-documento"' in body
    assert "placeholder=" not in body.split('id="titulo-documento"')[1][:400]
    # Va antes de «Líneas» (columna principal), no en la barra lateral.
    assert body.index('id="titulo-documento"') < body.index(">Líneas<")


def test_titulo_igual_al_automatico_se_guarda_vacio(cotizacion, entorno, client):
    """Devolver el texto tal cual no congela el título: sigue heredando."""
    client.force_login(entorno["admin"])
    r = client.post(
        f"/cotizaciones/{cotizacion.pk}/documento/",
        {"campo": "titulo_documento_manual",
         "valor_titulo_documento_manual": cotizacion.titulo_documento_auto},
    )
    assert r.status_code == 200
    cotizacion.refresh_from_db()
    assert cotizacion.titulo_documento_manual == ""


def test_titulo_editado_a_mano_si_se_guarda(cotizacion, entorno, client):
    client.force_login(entorno["admin"])
    r = client.post(
        f"/cotizaciones/{cotizacion.pk}/documento/",
        {"campo": "titulo_documento_manual",
         "valor_titulo_documento_manual": "Propuesta especial Ted Lasso"},
    )
    assert r.status_code == 200
    cotizacion.refresh_from_db()
    assert cotizacion.titulo_documento_manual == "Propuesta especial Ted Lasso"
    assert cotizacion.titulo_documento == "Propuesta especial Ted Lasso"


# ── 5. El botón del Dashboard ────────────────────────────────────────────────

def test_boton_del_dashboard_dice_resumir_pendientes(entorno, client):
    client.force_login(entorno["admin"])
    body = client.get("/").content.decode()
    assert "Resumir pendientes" in body
    assert "Resumir actividad" not in body
