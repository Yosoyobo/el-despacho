"""Cableado de envío por correo: cotización (enviar) y factura (emitir).

Mockea lib.cartero.enviar y services.generar_pdf — verifica que el envío se
dispara con el PDF adjunto y que el flujo nunca rompe por el correo.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def cot(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor, email_contacto="cliente@x.com")
    c = Cotizacion.objects.create(cliente=cli, titulo="Servicios", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=c, orden=0, descripcion="Diseño", cantidad=Decimal("1"),
        unidad="pieza", precio_unitario=Decimal("1000.00"))
    return c


def _pdf_ok():
    from lib.documentos import ResultadoPdf
    return ResultadoPdf(ok=True, data={"id": "P1"}, pdf_bytes=b"%PDF")


def test_cotizacion_enviar_por_correo_adjunta_pdf(cot, monkeypatch):
    from apps.cotizaciones import services

    from lib import cartero
    monkeypatch.setattr(services, "generar_pdf", lambda c, a: _pdf_ok())
    capt = {}
    monkeypatch.setattr(
        cartero, "enviar",
        lambda **kw: capt.update(kw) or cartero.ResultadoCorreo(ok=True, proveedor="n8n", detalle="ok"),
    )
    res = services.enviar_por_correo(cot, cot.creado_por, "cliente@x.com")
    assert res.ok
    assert capt["destinatario"] == "cliente@x.com"
    assert len(capt["adjuntos"]) == 1
    assert capt["adjuntos"][0].nombre == f"{cot.codigo}.pdf"


def test_cotizacion_sin_correo_de_cliente(cot, monkeypatch):
    from apps.cotizaciones import services
    cot.cliente.email_contacto = ""
    cot.cliente.save()
    res = services.enviar_por_correo(cot, cot.creado_por, "")
    assert res.ok is False
    assert "correo" in res.error.lower()


def test_cotizacion_enviar_sin_pdf_manda_igual(cot, monkeypatch):
    """Si Drive falla y no hay PDF, el correo sale sin adjunto."""
    from apps.cotizaciones import services

    from lib import cartero
    from lib.documentos import ResultadoPdf
    monkeypatch.setattr(services, "generar_pdf",
                        lambda c, a: ResultadoPdf(ok=False, error="sin Drive"))
    capt = {}
    monkeypatch.setattr(
        cartero, "enviar",
        lambda **kw: capt.update(kw) or cartero.ResultadoCorreo(ok=True),
    )
    res = services.enviar_por_correo(cot, cot.creado_por, "cliente@x.com")
    assert res.ok
    assert capt["adjuntos"] == []


def test_vista_enviar_marca_y_avisa(client, cot, monkeypatch):
    """La cotización se marca enviada aunque el correo falle (warning)."""
    from apps.cotizaciones import services

    from lib import cartero
    monkeypatch.setattr(services, "generar_pdf", lambda c, a: _pdf_ok())
    monkeypatch.setattr(
        cartero, "enviar",
        lambda **kw: cartero.ResultadoCorreo(ok=False, error="n8n caído"),
    )
    client.force_login(cot.creado_por)
    resp = client.post(f"/cotizaciones/{cot.pk}/enviar/", {"email_destino": "cliente@x.com"})
    assert resp.status_code in (204, 302)
    cot.refresh_from_db()
    assert cot.estado == "enviada"  # se marcó pese al fallo del correo


@pytest.fixture
def fac(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor, email_contacto="cliente@x.com")
    f = Factura.objects.create(cliente=cli, titulo="Servicios", creado_por=autor)
    FacturaItem.objects.create(
        factura=f, orden=0, descripcion="Diseño", cantidad=Decimal("1"),
        unidad="pieza", precio_unitario=Decimal("1000.00"))
    return f


def test_factura_enviar_por_correo_adjunta_pdf(fac, monkeypatch):
    from apps.facturacion import services

    from lib import cartero
    # LC #162: el correo adjunta el PDF del CFDI ALMACENADO (del PAC).
    monkeypatch.setattr(services, "pdf_bytes_almacenado", lambda f: b"%PDF")
    capt = {}
    monkeypatch.setattr(
        cartero, "enviar",
        lambda **kw: capt.update(kw) or cartero.ResultadoCorreo(ok=True, detalle="ok"),
    )
    res = services.enviar_por_correo(fac, fac.creado_por)
    assert res.ok
    assert capt["destinatario"] == "cliente@x.com"
    assert capt["adjuntos"][0].nombre == f"{fac.codigo}.pdf"
