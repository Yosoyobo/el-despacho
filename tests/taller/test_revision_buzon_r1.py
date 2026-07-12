"""Revisión del buzón — Ronda 1 (2026-07).

Cubre el fix del bug de facturas en $0.00 al ligar una cotización/proyecto sin
capturar líneas a mano, el concepto automático, y el botón «Ligar» del panel
de facturas del proyecto.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _cotizacion_con_lineas(cli, autor, *, total_linea=Decimal("13700.00")):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(cliente=cli, titulo="Summer Camp", creado_por=autor)
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Producción Summer Camp",
        cantidad=Decimal("1"), precio_unitario=total_linea,
    )
    return cot


# ── Fix del bug $0.00 ─────────────────────────────────────────────────────


def test_asegurar_lineas_desde_cotizacion_copia_items(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = _cotizacion_con_lineas(cli, autor)
    fac = Factura.objects.create(cliente=cli, cotizacion_origen=cot, concepto="X", creado_por=autor)
    assert fac.items.count() == 0  # arranca sin líneas (el bug)

    agrego = services.asegurar_lineas_desde_origen(fac)

    assert agrego is True
    assert fac.items.count() == 1
    assert fac.calcular_totales()["subtotal_items"] == Decimal("13700.00")


def test_asegurar_lineas_es_idempotente(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura, FacturaItem

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = _cotizacion_con_lineas(cli, autor)
    fac = Factura.objects.create(cliente=cli, cotizacion_origen=cot, concepto="X", creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Manual",
        cantidad=Decimal("2"), precio_unitario=Decimal("100.00"),
    )
    agrego = services.asegurar_lineas_desde_origen(fac)
    assert agrego is False
    assert fac.items.count() == 1  # no duplicó ni sobrescribió lo capturado a mano


def test_nueva_factura_desde_cotizacion_no_queda_en_cero(client, cliente_factory, usuario_factory):
    """El bug reportado: agregar una cotización en el form y guardar sin líneas
    a mano dejaba la factura en $0.00. Ahora hereda las líneas de la cotización."""
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    cot = _cotizacion_con_lineas(cli, autor)

    resp = client.post("/facturacion/nueva/", {
        "folio_numero": "777", "porcentaje_a_facturar": "100",
        "cliente": cli.pk, "proyecto": "", "cotizacion_origen": cot.pk,
        "concepto": "", "estado": "borrador",
        "fecha_emision": "2026-07-01", "fecha_vencimiento": "2026-07-31",
        "moneda": "MXN", "regimen_fiscal": "iva",
        "descuento_global_porcentaje": "0", "notas": "", "terminos": "",
        "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
    })
    assert resp.status_code == 302
    from apps.facturacion.models import Factura
    fac = Factura.objects.get(cotizacion_origen=cot)
    assert fac.items.count() == 1
    assert fac.calcular_totales()["subtotal_items"] == Decimal("13700.00")
    # Concepto automático desde el título de la cotización (no quedó vacío).
    assert fac.concepto


# ── Botón «Ligar» ─────────────────────────────────────────────────────────


def test_ligar_factura_a_proyecto(client, cliente_factory, usuario_factory, proyecto_factory):
    from apps.facturacion.models import Factura

    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor)
    fac = Factura.objects.create(cliente=cli, concepto="Suelta", creado_por=autor)
    assert fac.proyecto_id is None

    resp = client.post(f"/facturacion/ligar/{proy.pk}/", {"factura": fac.pk})
    assert resp.status_code in (204, 302)
    fac.refresh_from_db()
    assert fac.proyecto_id == proy.pk


def test_ligar_get_htmx_devuelve_modal(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    resp = client.get(f"/facturacion/ligar/{proy.pk}/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"Ligar" in resp.content
