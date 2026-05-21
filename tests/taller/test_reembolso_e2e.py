"""Test E2E del flujo completo de reembolso (bug #A sprint S-Finanzas-V2).

Verifica que tras reembolsar:
- El egreso queda 'pagado' con pagado_en y pagado_desde poblados.
- El asiento `auto_reembolso` se crea (D Reembolsos / H Banco|Caja).
- El saldo de Bancos efectivamente baja por el monto del egreso.
- Si el catálogo está incompleto, el service retorna flag de aviso
  pero NO tumba la transacción de Tesorería.
"""

from __future__ import annotations

from datetime import date
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
def centro():
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.create(
        nombre="General", slug="general", naturaleza="operativo", activo=True,
    )


def _crear_egreso_para_reembolsar(usuario, centro, monto=Decimal("500.00")):
    from apps.tesoreria.models import Egreso
    return Egreso.objects.create(
        monto=monto,
        fecha=date.today(),
        descripcion="Compra de insumos con tarjeta personal",
        centro_de_costo=centro,
        metodo="tarjeta_personal",
        estado_pago="por_reembolsar",
        origen="manual",
        pagado_por=usuario,
        creado_por=usuario,
    )


def test_reembolso_flujo_completo_actualiza_saldo_banco(usuario_factory, centro):
    """Ingreso $1000 a Banco → Egreso $500 por_reembolsar → Reembolso desde
    banco → saldo Banco queda en $500 ($1000 entró, $500 salió)."""
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    from apps.tesoreria import services
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="dueno")
    # Ingreso previo para llenar Banco
    Ingreso.objects.create(
        monto=Decimal("1000.00"),
        fecha=date.today(),
        descripcion="Cobro de cliente",
        metodo="transferencia",
        creado_por=u,
    )
    banco = cuenta_por_slot("banco")
    assert banco is not None
    saldo_inicial = saldo_cuenta(banco)
    assert saldo_inicial == Decimal("1000.00")

    # Egreso por reembolsar
    egreso = _crear_egreso_para_reembolsar(u, centro)

    # Reembolsar
    resultado = services.reembolsar_egreso(
        egreso, metodo="transferencia", banco_o_caja="banco",
        fecha=date.today(), actor=u,
    )

    egreso.refresh_from_db()
    assert egreso.estado_pago == "pagado"
    assert egreso.pagado_en == date.today()
    assert egreso.pagado_desde == "banco"
    assert getattr(resultado, "_reembolso_asiento_creado", False) is True

    saldo_final = saldo_cuenta(banco)
    assert saldo_final == Decimal("500.00"), (
        f"Banco debió bajar de $1000 a $500 (saldo: {saldo_final})"
    )


def test_reembolso_desde_caja_actualiza_caja(usuario_factory, centro):
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    from apps.tesoreria import services
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="dueno")
    Ingreso.objects.create(
        monto=Decimal("300.00"),
        fecha=date.today(),
        descripcion="Cobro efectivo",
        metodo="efectivo",
        creado_por=u,
    )
    caja = cuenta_por_slot("caja")
    assert saldo_cuenta(caja) == Decimal("300.00")

    egreso = _crear_egreso_para_reembolsar(u, centro, monto=Decimal("120"))
    services.reembolsar_egreso(
        egreso, metodo="efectivo", banco_o_caja="caja",
        fecha=date.today(), actor=u,
    )
    assert saldo_cuenta(caja) == Decimal("180.00")


def test_reembolso_sin_catalogo_no_tumba_estado(usuario_factory, centro):
    """Si la cuenta 'reembolsos' está desactivada (catalogo incompleto),
    el egreso igual pasa a pagado pero asiento_creado=False."""
    from apps.contaduria.models import CuentaContable
    from apps.tesoreria import services

    u = usuario_factory(rol="dueno")
    egreso = _crear_egreso_para_reembolsar(u, centro)
    # Desactivar cuenta reembolsos para simular catalogo incompleto
    CuentaContable.objects.filter(slot="reembolsos").update(activa=False)

    resultado = services.reembolsar_egreso(
        egreso, metodo="transferencia", banco_o_caja="banco",
        fecha=date.today(), actor=u,
    )
    egreso.refresh_from_db()
    assert egreso.estado_pago == "pagado"
    assert resultado._reembolso_asiento_creado is False
    assert "Catálogo incompleto" in getattr(resultado, "_reembolso_motivo_no_asiento", "")


def test_reembolso_aparece_en_detalle_egreso(client, usuario_factory, centro):
    """El detalle del egreso muestra fecha de pago y desde dónde."""
    from apps.tesoreria import services
    from django.urls import reverse

    u = usuario_factory(rol="dueno")
    egreso = _crear_egreso_para_reembolsar(u, centro)
    services.reembolsar_egreso(
        egreso, metodo="transferencia", banco_o_caja="banco",
        fecha=date(2026, 5, 21), actor=u,
    )
    client.force_login(u)
    resp = client.get(reverse("tesoreria:egreso-detalle", args=[egreso.pk]))
    assert resp.status_code == 200
    assert b"2026-05-21" in resp.content
    # "desde Banco" o variantes
    contenido = resp.content.decode()
    assert "Banco" in contenido and "Fecha de pago" in contenido


def test_migracion_0006_fuerza_activa_true(usuario_factory):
    """Tras correr migrate, todos los slots críticos están activos."""
    from apps.contaduria.models import CuentaContable
    slots_criticos = (
        "caja", "banco", "cxc", "cxp", "reembolsos",
        "ingreso_ventas", "egreso_operativo",
    )
    for slot in slots_criticos:
        c = CuentaContable.objects.filter(slot=slot).first()
        assert c is not None, f"falta cuenta con slot {slot}"
        assert c.activa, f"cuenta con slot {slot} debe estar activa tras migrate"
