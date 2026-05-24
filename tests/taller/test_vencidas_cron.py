"""Tests del cron de vencidas (cotizaciones + facturas).

Cubre:
- Las cotizaciones enviadas con fecha_validez < hoy se marcan y emiten evento.
- Las facturas emitidas con fecha_vencimiento < hoy idem.
- Idempotencia: segunda corrida no duplica eventos.
- Estados que no aplican (borrador, aprobada, cancelada, etc.) se ignoran.
- --dry-run no persiste.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def _spy_emisiones(monkeypatch):
    capturados = []

    def fake_emitir(evento):
        capturados.append(evento)

    monkeypatch.setattr("apps.cotizaciones.management.commands.marcar_cotizaciones_vencidas.emitir", fake_emitir)
    monkeypatch.setattr("apps.facturacion.management.commands.marcar_facturas_vencidas.emitir", fake_emitir)
    return capturados


def _cot(cliente, autor, *, estado, dias_atraso, validez_dias=None):
    from apps.cotizaciones.models import Cotizacion
    if validez_dias is None:
        validez_dias = -dias_atraso
    return Cotizacion.objects.create(
        cliente=cliente, titulo=f"Cot {estado}", estado=estado,
        fecha_validez=date.today() + timedelta(days=validez_dias),
        creado_por=autor,
    )


def _fac(cliente, autor, *, estado, dias_atraso):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(
        cliente=cliente, titulo=f"Fac {estado}", estado=estado,
        fecha_vencimiento=date.today() - timedelta(days=dias_atraso),
        creado_por=autor,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="X",
        cantidad=Decimal("1"), unidad="pieza",
        precio_unitario=Decimal("1000.00"),
    )
    return fac


def test_cotizacion_enviada_vencida_se_notifica(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = _cot(cli, autor, estado="enviada", dias_atraso=3)
    call_command("marcar_cotizaciones_vencidas", stdout=StringIO())
    cot.refresh_from_db()
    assert cot.vencida_notificada_en is not None
    tipos = [e.tipo for e in _spy_emisiones]
    assert tipos == ["cotizacion.vencida"]
    assert _spy_emisiones[0].payload["codigo"] == cot.codigo
    assert _spy_emisiones[0].payload["dias_vencida"] == 3


def test_cotizacion_borrador_no_se_notifica(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _cot(cli, autor, estado="borrador", dias_atraso=10)
    _cot(cli, autor, estado="aprobada", dias_atraso=10)
    call_command("marcar_cotizaciones_vencidas", stdout=StringIO())
    assert _spy_emisiones == []


def test_cotizacion_idempotente(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _cot(cli, autor, estado="enviada", dias_atraso=2)
    call_command("marcar_cotizaciones_vencidas", stdout=StringIO())
    call_command("marcar_cotizaciones_vencidas", stdout=StringIO())
    assert len(_spy_emisiones) == 1


def test_cotizacion_dry_run_no_persiste(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = _cot(cli, autor, estado="enviada", dias_atraso=1)
    call_command("marcar_cotizaciones_vencidas", "--dry-run", stdout=StringIO())
    cot.refresh_from_db()
    assert cot.vencida_notificada_en is None
    assert _spy_emisiones == []


def test_factura_emitida_vencida_se_notifica(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _fac(cli, autor, estado="emitida", dias_atraso=5)
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    fac.refresh_from_db()
    assert fac.vencida_notificada_en is not None
    tipos = [e.tipo for e in _spy_emisiones]
    assert tipos == ["factura.vencida"]
    assert _spy_emisiones[0].payload["dias_vencida"] == 5
    assert _spy_emisiones[0].payload["saldo_pendiente"] > 0


def test_factura_cobrada_total_no_se_notifica(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _fac(cli, autor, estado="cobrada_total", dias_atraso=10)
    _fac(cli, autor, estado="borrador", dias_atraso=10)
    _fac(cli, autor, estado="cancelada", dias_atraso=10)
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    assert _spy_emisiones == []


def test_factura_cobrada_parcial_si_se_notifica(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _fac(cli, autor, estado="cobrada_parcial", dias_atraso=2)
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    assert [e.tipo for e in _spy_emisiones] == ["factura.vencida"]


def test_factura_vencida_dispara_push_cobranza(cliente_factory, usuario_factory,
                                                 _spy_emisiones, monkeypatch):
    """Cuando el cron marca una factura como vencida, llama notificar_factura_vencida."""
    capturados = []

    def fake_notificar(factura, *, dias_vencida, saldo):
        capturados.append({"codigo": factura.codigo, "dias": dias_vencida, "saldo": saldo})

    monkeypatch.setattr(
        "apps.taller_home.push_handlers.notificar_factura_vencida",
        fake_notificar,
    )
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _fac(cli, autor, estado="emitida", dias_atraso=7)
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    assert len(capturados) == 1
    assert capturados[0]["dias"] == 7
    assert capturados[0]["saldo"] > 0


def test_categoria_cobranza_registrada():
    """La categoría 'cobranza' aparece en CATEGORIAS para admins/contador."""
    from apps.perfil_notificaciones.views import CATEGORIAS
    slugs = [c[0] for c in CATEGORIAS]
    assert "cobranza" in slugs


def test_factura_idempotente(cliente_factory, usuario_factory, _spy_emisiones):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _fac(cli, autor, estado="emitida", dias_atraso=2)
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    call_command("marcar_facturas_vencidas", stdout=StringIO())
    assert len(_spy_emisiones) == 1
