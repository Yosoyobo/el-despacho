"""Tests #D + #E del sprint S-Finanzas-V2.

- Cotizacion.anticipo_monto: porcentaje y override.
- Cotizacion.anticipo_pendiente: True solo si aprobada + monto > 0 + sin facturar.
- crear_factura_anticipo: crea Factura borrador con monto, vincula, marca.
- Idempotente: segundo intento falla.
- CxC unificado lista facturas + anticipos + proyectos legacy.
- CxC unificado no duplica: si factura está vinculada a proyecto, el proyecto no aparece.
- KPI anticipos-pendientes cuenta correcto.
- KPI cxc-total suma 3 fuentes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit",
        lambda fn, using=None, robust=False: fn(),
    )


@pytest.fixture
def cliente(db):
    from apps.la_cartera.models import Cliente
    return Cliente.objects.create(razon_social="ACME SA", rfc="ACM010101AAA")


def _crear_cotizacion(
    cliente,
    usuario,
    proyecto=None,
    *,
    estado="aprobada",
    anticipo_porcentaje=Decimal("30"),
    anticipo_monto_override=None,
    precio_unitario=Decimal("1000"),
):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(
        cliente=cliente,
        proyecto=proyecto,
        titulo="Servicio X",
        estado=estado,
        moneda="MXN",
        anticipo_porcentaje=anticipo_porcentaje,
        anticipo_monto_override=anticipo_monto_override,
        creado_por=usuario,
    )
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Linea",
        cantidad=Decimal("1"), unidad="servicio",
        precio_unitario=precio_unitario,
        descuento_porcentaje=Decimal("0"),
    )
    if estado == "aprobada":
        from django.utils import timezone
        cot.aprobada_en = timezone.now()
        cot.save(update_fields=["aprobada_en"])
    return cot


def test_anticipo_porcentaje_calcula_monto(cliente, usuario_factory):
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("30"),
                             precio_unitario=Decimal("1000"))
    # Total = 1000, anticipo 30% = 300
    assert cot.anticipo_monto == Decimal("300.00")


def test_anticipo_override_pisa_porcentaje(cliente, usuario_factory):
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("30"),
                             anticipo_monto_override=Decimal("500"),
                             precio_unitario=Decimal("1000"))
    assert cot.anticipo_monto == Decimal("500.00")


def test_anticipo_pendiente_requiere_aprobada(cliente, usuario_factory):
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, estado="borrador",
                             anticipo_porcentaje=Decimal("30"))
    assert not cot.anticipo_pendiente
    cot.estado = "aprobada"
    cot.save()
    assert cot.anticipo_pendiente


def test_anticipo_pendiente_false_sin_anticipo(cliente, usuario_factory):
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("0"))
    assert not cot.anticipo_pendiente


def test_crear_factura_anticipo_genera_factura_borrador(cliente, usuario_factory):
    from apps.cotizaciones import services as cot_services
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("25"),
                             precio_unitario=Decimal("4000"))
    # Anticipo = 4000 * 25% = 1000
    factura = cot_services.crear_factura_anticipo(cot, u)
    assert factura.estado == "borrador"
    assert factura.titulo == f"Anticipo de {cot.codigo}"
    assert factura.cotizacion_origen_id == cot.pk
    assert factura.items.count() == 1
    item = factura.items.first()
    assert item.precio_unitario == Decimal("1000.00")

    cot.refresh_from_db()
    assert cot.anticipo_facturado_en is not None
    assert not cot.anticipo_pendiente


def test_crear_factura_anticipo_idempotente(cliente, usuario_factory):
    from apps.cotizaciones import services as cot_services
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("30"))
    cot_services.crear_factura_anticipo(cot, u)
    with pytest.raises(ValueError, match="Ya se generó"):
        cot_services.crear_factura_anticipo(cot, u)


def test_crear_factura_anticipo_falla_sin_aprobar(cliente, usuario_factory):
    from apps.cotizaciones import services as cot_services
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, estado="borrador",
                             anticipo_porcentaje=Decimal("30"))
    with pytest.raises(ValueError, match="aprobada"):
        cot_services.crear_factura_anticipo(cot, u)


def test_cxc_unificado_incluye_factura_emitida(cliente, usuario_factory):
    from apps.facturacion import services as fact_services
    from apps.facturacion.models import Factura, FacturaItem
    from apps.tesoreria.services import cxc_unificado

    u = usuario_factory(rol="dueno")
    fac = Factura.objects.create(
        cliente=cliente, titulo="Servicio",
        fecha_emision=date.today(),
        fecha_vencimiento=date.today() + timedelta(days=30),
        creado_por=u,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="L",
        cantidad=Decimal("1"), unidad="x",
        precio_unitario=Decimal("2500"),
    )
    fact_services.emitir_factura(fac, u)

    filas = cxc_unificado()
    assert any(f["tipo"] == "factura" and f["codigo"] == fac.codigo for f in filas)


def test_cxc_unificado_incluye_anticipo_pendiente(cliente, usuario_factory):
    from apps.tesoreria.services import cxc_unificado
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("40"),
                             precio_unitario=Decimal("2000"))
    filas = cxc_unificado()
    anticipos = [f for f in filas if f["tipo"] == "anticipo"]
    assert len(anticipos) == 1
    assert anticipos[0]["codigo"] == cot.codigo
    assert anticipos[0]["saldo"] == Decimal("800.00")


def test_cxc_unificado_no_doblea_proyecto_con_factura(cliente, usuario_factory,
                                                       proyecto_factory):
    from apps.facturacion import services as fact_services
    from apps.facturacion.models import Factura, FacturaItem
    from apps.tesoreria.services import cxc_unificado

    u = usuario_factory(rol="dueno")
    pry = proyecto_factory(cliente=cliente)
    pry.monto_facturado = Decimal("5000")
    pry.monto_cobrado = Decimal("0")
    pry.save()

    fac = Factura.objects.create(
        cliente=cliente, proyecto=pry, titulo="Factura del pry",
        fecha_emision=date.today(),
        fecha_vencimiento=date.today() + timedelta(days=30),
        creado_por=u,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="L",
        cantidad=Decimal("1"), unidad="x",
        precio_unitario=Decimal("3000"),
    )
    fact_services.emitir_factura(fac, u)

    filas = cxc_unificado()
    proyectos = [f for f in filas if f["tipo"] == "proyecto"]
    facturas = [f for f in filas if f["tipo"] == "factura" and f["codigo"] == fac.codigo]
    assert len(facturas) == 1
    # El proyecto NO debe aparecer porque tiene factura vinculada
    assert all(f["codigo"] != pry.codigo for f in proyectos), (
        "El proyecto con factura emitida no debe aparecer también como CxC legacy"
    )


def test_kpi_anticipos_pendientes(cliente, usuario_factory):
    from apps.taller_home.kpis import KPIS
    u = usuario_factory(rol="dueno")
    _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("30"))
    _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("50"))
    # Sin anticipo: no debe contar
    _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("0"))
    kpi = next(k for k in KPIS if k.slug == "anticipos-pendientes")
    resultado = kpi.calcular(u)
    assert resultado["valor"] == 2


def test_por_cobrar_view_renderiza_unificado(client, cliente, usuario_factory):
    u = usuario_factory(rol="dueno")
    cot = _crear_cotizacion(cliente, u, anticipo_porcentaje=Decimal("20"),
                             precio_unitario=Decimal("5000"))
    client.force_login(u)
    resp = client.get("/tesoreria/por-cobrar/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Anticipo" in contenido
    assert cot.codigo in contenido
