"""La Cobranza — recordatorios automáticos de pago al cliente (S3 resto)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture(autouse=True)
def _cartero_ok(monkeypatch):
    """Neutraliza el envío real de correo: El Cartero devuelve OK."""
    from lib import cartero
    monkeypatch.setattr(
        cartero, "enviar",
        lambda **kw: cartero.ResultadoCorreo(ok=True, proveedor="n8n", detalle="mock"),
    )


def _factura_vencida(cliente, autor, *, dias_vencida=10, monto="1000.00", email="cliente@x.mx"):
    from apps.facturacion.models import Factura, FacturaItem
    cliente.email_contacto = email
    cliente.save(update_fields=["email_contacto"])
    fac = Factura.objects.create(
        cliente=cliente, titulo="Factura", estado="emitida",
        fecha_emision=date.today() - timedelta(days=dias_vencida + 30),
        fecha_vencimiento=date.today() - timedelta(days=dias_vencida),
        creado_por=autor,
    )
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Servicio",
        cantidad=Decimal("1"), precio_unitario=Decimal(monto),
    )
    return fac


def _config(**kw):
    from ajustes.models import ConfiguracionCobranza
    cfg = ConfiguracionCobranza.obtener()
    for k, v in kw.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


def test_facturas_a_recordar_encuentra_vencidas(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _factura_vencida(cli, autor, dias_vencida=15)
    cfg = _config(activa=True)
    pendientes = cobranza.facturas_a_recordar(config=cfg)
    assert len(pendientes) == 1
    assert pendientes[0]["tipo"] == "mora"


def test_no_recuerda_si_no_vencida(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    from apps.facturacion.models import Factura, FacturaItem
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor, email_contacto="c@x.mx")
    fac = Factura.objects.create(
        cliente=cli, titulo="F", estado="emitida",
        fecha_vencimiento=date.today() + timedelta(days=20), creado_por=autor,
    )
    FacturaItem.objects.create(factura=fac, orden=0, descripcion="x",
                               cantidad=Decimal("1"), precio_unitario=Decimal("100"))
    cfg = _config(activa=True, recordar_pre_vencimiento_dias=0)
    assert cobranza.facturas_a_recordar(config=cfg) == []


def test_enviar_recordatorio_audita_ok(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    from apps.facturacion.models import RecordatorioCobranza
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_vencida(cli, autor)
    rec = cobranza.enviar_recordatorio(fac, tipo="mora")
    assert rec.ok is True
    assert rec.destinatario == "cliente@x.mx"
    assert RecordatorioCobranza.objects.filter(factura=fac, ok=True).count() == 1


def test_enviar_recordatorio_sin_correo_falla_grácil(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_vencida(cli, autor, email="")
    rec = cobranza.enviar_recordatorio(fac, tipo="mora")
    assert rec.ok is False
    assert "correo" in rec.detalle.lower()


def test_cadencia_no_repite_antes_de_tiempo(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_vencida(cli, autor, dias_vencida=15)
    cfg = _config(activa=True, dias_entre_recordatorios=7)
    cobranza.enviar_recordatorio(fac, config=cfg, tipo="mora")
    # Justo después, no debe volver a tocar.
    assert cobranza.facturas_a_recordar(config=cfg) == []


def test_tope_max_recordatorios(cliente_factory, usuario_factory):
    from apps.facturacion import cobranza
    from apps.facturacion.models import RecordatorioCobranza
    from django.utils import timezone
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_vencida(cli, autor, dias_vencida=40)
    cfg = _config(activa=True, dias_entre_recordatorios=1, max_recordatorios=2)
    # Simula 2 recordatorios ya enviados hace tiempo (no bloquea por cadencia).
    viejo = timezone.now() - timezone.timedelta(days=10)
    for _ in range(2):
        r = RecordatorioCobranza.objects.create(factura=fac, ok=True, tipo="mora")
        RecordatorioCobranza.objects.filter(pk=r.pk).update(enviado_en=viejo)
    assert cobranza.facturas_a_recordar(config=cfg) == []


def test_command_apagado_no_envia(cliente_factory, usuario_factory):
    from io import StringIO

    from apps.facturacion.models import RecordatorioCobranza
    from django.core.management import call_command
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _factura_vencida(cli, autor, dias_vencida=20)
    _config(activa=False)
    out = StringIO()
    call_command("enviar_recordatorios_cobranza", stdout=out)
    assert "DESACTIVADA" in out.getvalue()
    assert RecordatorioCobranza.objects.count() == 0


def test_command_envia_cuando_activa(cliente_factory, usuario_factory):
    from io import StringIO

    from apps.facturacion.models import RecordatorioCobranza
    from django.core.management import call_command
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    _factura_vencida(cli, autor, dias_vencida=20)
    _config(activa=True)
    call_command("enviar_recordatorios_cobranza", stdout=StringIO())
    assert RecordatorioCobranza.objects.filter(ok=True).count() == 1
