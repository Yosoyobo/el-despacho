"""Régimen de honorarios RESICO (IVA + retenciones) — Anexo 20 SAT.

Valida al CENTAVO el caso de auditoría de Oscar. Sprint Fiscal 2026-07: cada
impuesto se calcula INDEPENDIENTE = Base × tasa nominal / 100, redondeado al
final (la retención de IVA ya NO es fracción ⅔ del IVA redondeado):

    Importe (subtotal)     33,770.00
    + IVA 16%               5,403.20   (33,770 × 16%      = 5,403.20)
    - Ret. ISR 1.25%          422.13   (33,770 × 1.25%    = 422.125  → 422.13)
    - Ret. IVA 10.6667%     3,602.14   (33,770 × 10.6667% = 3,602.14…)
    = Total neto           35,148.93

Cubre: motor puro (lib.fiscal), factura y cotización en régimen honorarios,
redondeo HALF_UP (no HALF_EVEN), herencia proyecto→cotización→factura, el
asiento contable de emisión cuadra, y eliminar factura cancelada. Incluye
3 facturas reales de Oscar como red de seguridad del método nominal.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

BASE = Decimal("33770.00")
IVA = Decimal("5403.20")
RET_ISR = Decimal("422.13")
RET_IVA = Decimal("3602.14")
TOTAL = Decimal("35148.93")


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


# ── Motor puro ────────────────────────────────────────────────────────────


def test_desglose_honorarios_al_centavo():
    from lib.fiscal import desglose_honorarios
    d = desglose_honorarios(BASE)
    assert d["iva"] == IVA
    assert d["ret_isr"] == RET_ISR
    assert d["ret_iva"] == RET_IVA
    assert d["retenciones"] == RET_ISR + RET_IVA
    assert d["trasladados"] == IVA
    assert d["total"] == TOTAL


def test_q2_redondea_half_up():
    """El bug previo: 422.125 con HALF_EVEN da 422.12; la convención fiscal MX
    (HALF_UP) da 422.13."""
    from lib.fiscal import q2
    assert q2(Decimal("422.125")) == Decimal("422.13")
    assert q2(Decimal("0.125")) == Decimal("0.13")
    assert q2(Decimal("0.135")) == Decimal("0.14")


def test_ret_iva_es_tasa_nominal_sobre_base():
    """Anexo 20 SAT: la retención de IVA = Base × 10.6667% (tasa nominal),
    independiente y redondeada al final. NO es fracción del IVA redondeado
    (⅔ × 5,403.20 = 3,602.13, que no cuadra con el PAC), ni un % de 2 decimales
    sobre la base (10.67% = 3,603.26 / 10.66% = 3,599.88)."""
    from lib.fiscal import desglose_honorarios
    d = desglose_honorarios(BASE)
    # 33,770 × 10.6667% = 3,602.1446… → 3,602.14
    assert d["ret_iva"] == RET_IVA
    assert d["ret_iva"] == Decimal("3602.14")
    assert d["ret_iva"] != Decimal("3602.13")  # el viejo método ⅔ del IVA
    assert d["ret_iva"] != Decimal("3603.26")  # 10.67% (2 decimales)
    assert d["ret_iva"] != Decimal("3599.88")  # 10.66% (2 decimales)


@pytest.mark.parametrize(
    ("base", "ret_iva", "total"),
    [
        # Facturas reales verificadas por Oscar (Base → Ret. IVA → Total neto).
        (Decimal("33770.00"), Decimal("3602.14"), Decimal("35148.93")),
        (Decimal("16000.00"), Decimal("1706.67"), Decimal("16653.33")),
        (Decimal("40184.22"), Decimal("4286.33"), Decimal("41825.07")),
    ],
)
def test_facturas_reales_al_centavo(base, ret_iva, total):
    """Base × 10.6667% (ret. IVA) e importe neto, verificados contra facturas
    reales del despacho. Total = Base + IVA 16% − ISR 1.25% − ret. IVA."""
    from lib.fiscal import desglose_honorarios
    d = desglose_honorarios(base)
    assert d["ret_iva"] == ret_iva
    assert d["total"] == total


# ── Factura ────────────────────────────────────────────────────────────────


def test_factura_honorarios_al_centavo(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(
        cliente=cli, titulo="Honorarios", regimen_fiscal="honorarios", creado_por=autor,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Honorarios profesionales",
        cantidad=Decimal("1"), precio_unitario=BASE,
    )
    t = fac.calcular_totales()
    assert t["base_impuestos"] == BASE
    assert t["trasladados"] == IVA
    assert t["retenciones"] == RET_ISR + RET_IVA
    assert t["total"] == TOTAL
    tipos = {(d["tipo"], d["monto"]) for d in t["impuestos_detalle"]}
    assert ("trasladado", IVA) in tipos
    assert ("retencion", RET_ISR) in tipos
    assert ("retencion", RET_IVA) in tipos


def test_factura_honorarios_asiento_cuadra(cliente_factory, usuario_factory):
    from apps.contaduria.models import Asiento
    from apps.facturacion import services
    from apps.facturacion.models import Factura, FacturaItem

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(
        cliente=cli, titulo="Honorarios", regimen_fiscal="honorarios", creado_por=autor,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Honorarios", cantidad=Decimal("1"), precio_unitario=BASE,
    )
    services.emitir_factura(fac, autor)
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"facturacion.factura:{fac.pk}", origen="auto_factura_emitida",
    ).first()
    assert asiento is not None
    cargos = sum(p.cargo for p in asiento.partidas.all())
    abonos = sum(p.abono for p in asiento.partidas.all())
    assert cargos == abonos == Decimal("39173.20")
    slots_cargo = {p.cuenta.slot for p in asiento.partidas.filter(cargo__gt=0)}
    slots_abono = {p.cuenta.slot for p in asiento.partidas.filter(abono__gt=0)}
    assert "cxc" in slots_cargo
    assert "isr_retenido" in slots_cargo
    assert "iva_retenido_pagar" in slots_cargo
    assert "ingreso_ventas" in slots_abono
    assert "iva_trasladado" in slots_abono
    # La CxC (lo que debe el cliente) es el neto a pagar.
    cxc = asiento.partidas.get(cuenta__slot="cxc")
    assert cxc.cargo == TOTAL


# ── Cotización ──────────────────────────────────────────────────────────────


def test_cotizacion_honorarios_al_centavo(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = Cotizacion.objects.create(
        cliente=cli, titulo="Honorarios", regimen_fiscal="honorarios", creado_por=autor,
    )
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Honorarios", cantidad=Decimal("1"), precio_unitario=BASE,
    )
    t = cot.calcular_totales()
    assert t["base_impuestos"] == BASE
    assert t["trasladados"] == IVA
    assert t["retenciones"] == RET_ISR + RET_IVA
    assert t["total"] == TOTAL


# ── Herencia proyecto → cotización → factura ────────────────────────────────


def test_regimen_heredado_proyecto_a_cotizacion(cliente_factory, usuario_factory):
    from apps.cotizaciones.services import generar_desde_proyecto
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(
        nombre="Consultoría", cliente=cli, regimen_fiscal="honorarios", creado_por=autor,
    )
    cot = generar_desde_proyecto(proy, autor)
    assert cot.regimen_fiscal == "honorarios"
    # No debe tener tasas M2M (el cálculo honorarios no las usa).
    assert cot.impuestos.count() == 0


def test_proyecto_desglose_fiscal_honorarios(cliente_factory, usuario_factory):
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(
        nombre="Consultoría", cliente=cli, regimen_fiscal="honorarios", creado_por=autor,
    )
    # Sin productos, monto_calculado = 0 → todo 0.
    d = proy.desglose_fiscal
    assert d["regimen"] == "honorarios"
    assert d["total"] == Decimal("0.00")


# ── Eliminar factura cancelada ──────────────────────────────────────────────


def test_eliminar_factura_cancelada(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, titulo="Prueba", creado_por=autor)
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="X", cantidad=Decimal("1"), precio_unitario=Decimal("100"),
    )
    pk = fac.pk
    services.cancelar(fac, autor, "error de captura")
    services.eliminar(fac, autor)
    assert not Factura.objects.filter(pk=pk).exists()


def test_no_eliminar_factura_no_cancelada(cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.facturacion.models import Factura
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = Factura.objects.create(cliente=cli, titulo="Viva", creado_por=autor)
    with pytest.raises(ValueError):
        services.eliminar(fac, autor)
