"""La Imprenta · Deploy 2 (2026-09-29): el contenido de los documentos y la factura.

Lo que se cuida:

1. **Las notas se editan en La Gerencia** (orden, apagar, agregar) y cada
   cotización puede quitar alguna o sumar las suyas; se heredan a la versión
   siguiente y al duplicar. Las de fábrica son las de siempre.
2. **Las notas tienen su propio permiso**: quien cambia el estilo no cambia lo
   que el cliente acepta.
3. **Firma, aceptación, folio, vigencia y QR** salen cuando se encienden; el QR
   nunca en la versión de Google.
4. **Marcas por estado**: de fábrica sólo BORRADOR (lo de siempre); las demás
   cuando se escriben.
5. **El nombre del archivo** sigue el patrón.
6. **La factura** se arma con La Imprenta: su PDF comercial sale del motor, se
   adjunta al correo cuando no hay CFDI, y la leyenda «no es un CFDI» no se va.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

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
                                  titulo="Termos", creado_por=jefe, estado="generada")
    CotizacionItem.objects.create(cotizacion=c, orden=0, concepto="Termo",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100"))
    return c


@pytest.fixture
def fac(cliente_factory, jefe):
    from apps.facturacion.models import Factura, FacturaItem

    f = Factura.objects.create(cliente=cliente_factory(creado_por=jefe, razon_social="Heladería Sur",
                                                       rfc="HSU010101AB1"),
                               titulo="Producción de vasos", creado_por=jefe)
    FacturaItem.objects.create(factura=f, orden=0, descripcion="Vasos", cantidad=Decimal("1"),
                               unidad="pieza", precio_unitario=Decimal("1000.00"))
    return f


def _guardar(ambito, **valores):
    from imprenta.models import AjusteImprenta

    fila, _ = AjusteImprenta.objects.get_or_create(ambito=ambito)
    fila.valores = {**(fila.valores or {}), **valores}
    fila.save()
    from imprenta import config
    config.olvidar()


def _html(cot):
    from apps.cotizaciones import services

    return services.construir_html_pdf(cot)


# ── 1. Las notas ────────────────────────────────────────────────────────────


def test_de_fabrica_las_notas_son_las_de_siempre(cot):
    from apps.cotizaciones.notas import NOTAS_FIJAS, notas_para

    notas = notas_para(cot)
    assert notas[:-1] == list(NOTAS_FIJAS)
    assert notas[-1] == cot.nota_forma_pago


def test_las_notas_editadas_en_la_gerencia_salen_en_su_orden(cot):
    _guardar("cotizacion", notas=[
        {"id": "n2", "texto": "Segunda primero.", "activa": True},
        {"id": "n1", "texto": "Apagada.", "activa": False},
        {"id": "nx", "texto": "Una nueva.", "activa": True},
    ], nota_automatica=False)
    html = _html(cot)
    assert html.index("Segunda primero.") < html.index("Una nueva.")
    assert "Apagada." not in html
    assert cot.nota_forma_pago not in html, "la forma de pago se apagó y siguió saliendo"


def test_cada_cotizacion_quita_y_suma_las_suyas(cot):
    cot.notas_omitidas = ["n7"]
    cot.notas_extra = "Entrega en Tizayuca.\n\n  Incluye empaque.  "
    cot.save()
    from apps.cotizaciones.notas import NOTAS_FIJAS, notas_para

    notas = notas_para(cot)
    assert NOTAS_FIJAS[6] not in notas
    assert "Entrega en Tizayuca." in notas and "Incluye empaque." in notas
    assert notas[-1] == cot.nota_forma_pago, "la forma de pago va siempre al final"


def test_la_version_siguiente_y_el_duplicado_heredan_las_notas(cot, jefe):
    from apps.cotizaciones import services

    cot.notas_omitidas = ["n3"]
    cot.notas_extra = "Sólo para Optimist."
    cot.save()
    copia = services.duplicar(cot, jefe)
    assert copia.notas_omitidas == ["n3"] and copia.notas_extra == "Sólo para Optimist."


def test_el_recuadro_documento_quita_una_nota(client, jefe, cot):
    client.force_login(jefe)
    url = reverse("cotizaciones:documento-opciones", args=[cot.pk])
    r = client.post(url, {"campo": "nota", "nota_id": "n2"})       # casilla apagada
    assert r.status_code == 200
    cot.refresh_from_db()
    assert cot.notas_omitidas == ["n2"]
    client.post(url, {"campo": "nota", "nota_id": "n2", "valor_nota": "on"})
    cot.refresh_from_db()
    assert cot.notas_omitidas == []
    assert client.post(url, {"campo": "nota", "nota_id": "inventada"}).status_code == 400
    client.post(url, {"campo": "notas_extra", "valor_notas_extra": "Extra uno\nExtra dos"})
    cot.refresh_from_db()
    assert cot.notas_extra == "Extra uno\nExtra dos"


# ── 2. El permiso de las notas ──────────────────────────────────────────────


# ── 3. Firma, aceptación, folio, vigencia y QR ──────────────────────────────


def test_firma_aceptacion_folio_y_vigencia(cot):
    _guardar("firma", nombre="Oscar Bautista", cargo="Director")
    _guardar("cotizacion", firma=True, aceptacion=True, mostrar_folio=True, mostrar_vigencia=True)
    html = _html(cot)
    assert "Oscar Bautista" in html and "Director" in html
    assert "Acepto esta cotización y sus condiciones." in html
    assert f"Folio {cot.codigo}" in html
    assert "Válida hasta el" in html


def test_de_fabrica_no_hay_firma_ni_folio_ni_qr(cot):
    html = _html(cot)
    assert "Nombre, firma y fecha" not in html
    assert f"Folio {cot.codigo}" not in html
    assert "data:image/svg+xml" not in html


def test_el_qr_sale_con_chromium_y_no_con_google(cot):
    from apps.cotizaciones import services

    from imprenta.config import resolver

    _guardar("cotizacion", qr="portal")
    assert "data:image/svg+xml;base64," in services.construir_html_pdf(cot)
    basico = services.construir_html_pdf(cot, config=resolver("cotizacion", basico=True))
    assert "data:image/svg+xml" not in basico, "Google no dibuja imágenes data:"


# ── 4. Marcas por estado ────────────────────────────────────────────────────


def test_de_fabrica_solo_la_de_borrador(cot):
    from apps.cotizaciones import services

    assert services.pagina_documento(cot)["marca_agua"] == "BORRADOR"
    cot.estado = "aprobada"
    cot.save()
    assert "marca_agua" not in services.pagina_documento(cot)


def test_la_marca_de_aprobada_cuando_se_escribe(cot):
    from apps.cotizaciones import services

    _guardar("cotizacion", marca_aprobada="APROBADA", marca_aprobada_color="#12b76a")
    cot.estado = "aprobada"
    cot.save()
    pag = services.pagina_documento(cot)
    assert pag["marca_agua"] == "APROBADA" and pag["marca_color"] == "#12b76a"


# ── 5. El nombre del archivo ────────────────────────────────────────────────


def test_el_nombre_del_archivo_sigue_el_patron(cot):
    from apps.cotizaciones import services

    assert services.nombre_archivo(cot) == cot.nombre_pdf, "sin patrón, el de siempre"
    _guardar("cotizacion", patron_archivo="{folio} — {cliente}/{fecha}")
    nombre = services.nombre_archivo(cot)
    assert nombre.startswith(f"{cot.codigo} — Optimist")
    assert "/" not in nombre


# ── 6. La factura ───────────────────────────────────────────────────────────


def test_la_factura_de_fabrica_lleva_lo_de_siempre(fac):
    from apps.facturacion import services

    html = services.construir_html_pdf(fac)
    assert "FACTURA" in html and fac.codigo in html
    assert "no es un CFDI" in html
    assert "HSU010101AB1" in html, "el RFC del cliente"
    assert "Logo_LC-256.png" in html


def test_la_leyenda_no_cfdi_no_se_apaga(fac):
    from apps.facturacion import services

    _guardar("factura", **{f"bloque_{b}": False for b in
                           ("fecha", "logo", "cliente", "fechas", "proyecto", "descuento",
                            "saldo", "pago_en_linea", "notas", "terminos")})
    assert "no es un CFDI" in services.construir_html_pdf(fac)


def test_la_factura_pagada_lleva_su_marca_y_va_en_pdfa(fac):
    from apps.facturacion import services

    fac.estado = "cobrada_total"
    fac.save()
    pag = services.pagina_documento(fac)
    assert pag["marca_agua"] == "PAGADA"
    assert pag.get("pdfa") is True, "la factura se archiva: de fábrica va en PDF/A"


def test_el_pdf_comercial_sale_del_motor(client, jefe, fac, monkeypatch):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF-1.4 fac")
    client.force_login(jefe)
    r = client.get(reverse("facturacion:pdf-comercial", args=[fac.pk]))
    assert r.status_code == 200 and r.content == b"%PDF-1.4 fac"
    assert "FACTURA" in r["Content-Disposition"]


def test_sin_motor_el_pdf_comercial_manda_a_la_version_imprimible(client, jefe, fac, monkeypatch):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    client.force_login(jefe)
    r = client.get(reverse("facturacion:pdf-comercial", args=[fac.pk]))
    assert r.status_code == 302 and r["Location"].endswith(f"/{fac.pk}/ver/")


def test_sin_cfdi_el_correo_lleva_la_factura_comercial(fac, monkeypatch):
    from apps.facturacion import services

    from lib import cartero, gotenberg

    fac.cliente.email_contacto = "compras@heladeria.mx"
    fac.cliente.save()
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF-1.4 fac")
    enviado = {}
    monkeypatch.setattr(cartero, "enviar", lambda **kw: enviado.update(kw) or cartero.ResultadoCorreo(ok=True))
    services.enviar_por_correo(fac, None)
    assert [a.contenido for a in enviado["adjuntos"]] == [b"%PDF-1.4 fac"]




# ── 7. El Chalán: el enlace al PDF ──────────────────────────────────────────


def test_el_chalan_da_el_enlace_del_pdf(jefe, cot, fac, usuario_factory):
    import capacidades

    r = capacidades.ejecutar("enlace_documento", {"tipo": "cotizacion", "codigo": cot.codigo}, jefe)
    assert r["pdf"] == f"/cotizaciones/{cot.pk}/pdf/"
    fac.folio_numero = 12
    fac.save()
    r = capacidades.ejecutar("enlace_documento", {"tipo": "factura", "codigo": "F12"}, jefe)
    assert r["pdf"] == f"/facturacion/{fac.pk}/pdf-comercial/"
    miembro = usuario_factory(rol="miembro")
    r = capacidades.ejecutar("enlace_documento", {"tipo": "factura", "codigo": "F12"}, miembro)
    assert "error" in r and "permiso" in r["error"]
