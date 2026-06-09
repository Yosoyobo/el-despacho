"""PDF de Cotizaciones y Facturas vía Google Docs (S-Drive-Cierre).

- `construir_html_pdf` renderiza el template sin error (cubre pdf.html).
- `services.generar_pdf` actualiza los campos del modelo cuando Drive responde.
- La vista descarga el PDF (200 application/pdf) o degrada con mensaje si Drive
  no está conectado (302 al detalle) — fallback gracioso.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _resultado_fake(pdf=b"%PDF-1.4 fake"):
    from lib.documentos import ResultadoPdf
    return ResultadoPdf(
        ok=True,
        data={"id": "DRIVEPDF1", "webViewLink": "http://drive/DRIVEPDF1"},
        pdf_bytes=pdf,
    )


@pytest.fixture
def cot_borrador(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(cliente=cli, titulo="Servicios mayo", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Diseño",
        cantidad=Decimal("2"), unidad="pieza", precio_unitario=Decimal("1500.00"),
    )
    return cot


# ── Cotizaciones ────────────────────────────────────────────────────────

def test_cotizacion_construir_html_pdf_renderiza(cot_borrador):
    from apps.cotizaciones import services
    html = services.construir_html_pdf(cot_borrador)
    assert cot_borrador.codigo in html
    assert "COTIZACIÓN" in html
    assert "Learning Center" in html


def test_cotizacion_generar_pdf_actualiza_modelo(cot_borrador, monkeypatch):
    from apps.cotizaciones import services
    monkeypatch.setattr("lib.documentos.generar_pdf",
                        lambda **kw: _resultado_fake())
    res = services.generar_pdf(cot_borrador, cot_borrador.creado_por)
    assert res.ok
    cot_borrador.refresh_from_db()
    assert cot_borrador.pdf_file_id == "DRIVEPDF1"
    assert cot_borrador.pdf_url == "http://drive/DRIVEPDF1"
    assert cot_borrador.pdf_generado_en is not None


def test_cotizacion_vista_pdf_descarga(client, cot_borrador, monkeypatch):
    from apps.cotizaciones import services
    monkeypatch.setattr(services, "generar_pdf", lambda cot, actor: _resultado_fake())
    client.force_login(cot_borrador.creado_por)
    resp = client.get(f"/cotizaciones/{cot_borrador.pk}/pdf/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_cotizacion_vista_pdf_sin_drive_degrada(client, cot_borrador):
    # Sin credenciales de Drive en el entorno de test → ok=False, redirige.
    client.force_login(cot_borrador.creado_por)
    resp = client.get(f"/cotizaciones/{cot_borrador.pk}/pdf/")
    assert resp.status_code == 302
    assert f"/cotizaciones/{cot_borrador.pk}/" in resp["Location"]


# ── Facturas ──────────────────────────────────────────────────────────────

@pytest.fixture
def fac_borrador(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, titulo="Servicios mayo", creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Diseño",
        cantidad=Decimal("1"), unidad="pieza", precio_unitario=Decimal("1000.00"),
    )
    return fac


def test_factura_construir_html_pdf_renderiza(fac_borrador):
    from apps.facturacion import services
    html = services.construir_html_pdf(fac_borrador)
    assert fac_borrador.codigo in html
    assert "FACTURA" in html
    assert "no es un CFDI" in html  # aviso de documento no fiscal


def test_factura_generar_pdf_actualiza_modelo(fac_borrador, monkeypatch):
    from apps.facturacion import services
    monkeypatch.setattr("lib.documentos.generar_pdf",
                        lambda **kw: _resultado_fake())
    res = services.generar_pdf(fac_borrador, fac_borrador.creado_por)
    assert res.ok
    fac_borrador.refresh_from_db()
    assert fac_borrador.pdf_file_id == "DRIVEPDF1"
    assert fac_borrador.pdf_generado_en is not None


def test_factura_vista_pdf_descarga(client, fac_borrador, monkeypatch):
    from apps.facturacion import services
    monkeypatch.setattr(services, "generar_pdf", lambda fac, actor: _resultado_fake())
    client.force_login(fac_borrador.creado_por)
    resp = client.get(f"/facturacion/{fac_borrador.pk}/pdf/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
