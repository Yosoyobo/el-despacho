"""Tests del flujo de reembolsar egreso dummy (Tesorería + Contaduría)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """En tests con db fixture, transaction.on_commit no se dispara porque
    la tx hace rollback. Forzamos ejecución inmediata para validar signals
    que generan asientos contables."""
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit",
        lambda fn, using=None, robust=False: fn(),
    )


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


@pytest.fixture
def egreso_por_reembolsar(db, usuario_factory, centro):
    from apps.tesoreria.models import Egreso
    empleado = usuario_factory(rol="disenador")
    egreso = Egreso.objects.create(
        monto=Decimal("250.00"), fecha=date.today(),
        descripcion="Compra de cartulinas", centro_de_costo=centro,
        pagado_por=empleado, creado_por=empleado,
        estado_pago="por_reembolsar", metodo="tarjeta_personal",
    )
    return egreso


# ── Service ──────────────────────────────────────────────────────────────


def test_reembolsar_egreso_cambia_estado_y_genera_asiento_banco(
    egreso_por_reembolsar, usuario_factory,
):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.services import reembolsar_egreso

    actor = usuario_factory(rol="dueno")
    reembolsar_egreso(
        egreso_por_reembolsar,
        metodo="transferencia", banco_o_caja="banco",
        fecha=date.today(), actor=actor,
    )
    egreso_por_reembolsar.refresh_from_db()
    assert egreso_por_reembolsar.estado_pago == "pagado"
    assert egreso_por_reembolsar.metodo == "transferencia"

    ref = f"tesoreria.egreso.reembolso:{egreso_por_reembolsar.pk}"
    asiento = Asiento.vigentes.get(referencia_externa=ref)
    assert asiento.origen == "auto_reembolso"
    partidas = list(asiento.partidas.all())
    assert len(partidas) == 2
    cargo = next(p for p in partidas if p.cargo > 0)
    abono = next(p for p in partidas if p.abono > 0)
    assert cargo.cuenta.slot == "reembolsos"
    assert abono.cuenta.slot == "banco"
    assert cargo.cargo == Decimal("250.00")
    assert abono.abono == Decimal("250.00")


def test_reembolsar_egreso_caja_efectivo(egreso_por_reembolsar, usuario_factory):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.services import reembolsar_egreso

    actor = usuario_factory(rol="dueno")
    reembolsar_egreso(
        egreso_por_reembolsar,
        metodo="efectivo", banco_o_caja="caja",
        fecha=date.today(), actor=actor,
    )
    ref = f"tesoreria.egreso.reembolso:{egreso_por_reembolsar.pk}"
    asiento = Asiento.vigentes.get(referencia_externa=ref)
    abono = next(p for p in asiento.partidas.all() if p.abono > 0)
    assert abono.cuenta.slot == "caja"


def test_reembolsar_egreso_ya_pagado_falla(egreso_por_reembolsar, usuario_factory):
    from apps.tesoreria.services import reembolsar_egreso
    egreso_por_reembolsar.estado_pago = "pagado"
    egreso_por_reembolsar.save(update_fields=["estado_pago", "actualizado_en"])
    with pytest.raises(ValueError):
        reembolsar_egreso(
            egreso_por_reembolsar,
            metodo="transferencia", banco_o_caja="banco",
            fecha=date.today(), actor=usuario_factory(rol="dueno"),
        )


def test_reembolsar_egreso_anulado_falla(egreso_por_reembolsar, usuario_factory):
    from apps.tesoreria.services import reembolsar_egreso
    egreso_por_reembolsar.anulado = True
    egreso_por_reembolsar.save(update_fields=["anulado", "actualizado_en"])
    with pytest.raises(ValueError):
        reembolsar_egreso(
            egreso_por_reembolsar,
            metodo="transferencia", banco_o_caja="banco",
            fecha=date.today(), actor=usuario_factory(rol="dueno"),
        )


def test_reembolsar_egreso_idempotente_no_duplica_asiento(
    egreso_por_reembolsar, usuario_factory,
):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.services import reembolsar_egreso

    actor = usuario_factory(rol="dueno")
    reembolsar_egreso(
        egreso_por_reembolsar,
        metodo="transferencia", banco_o_caja="banco",
        fecha=date.today(), actor=actor,
    )
    ref = f"tesoreria.egreso.reembolso:{egreso_por_reembolsar.pk}"
    n_antes = Asiento.objects.filter(referencia_externa=ref).count()
    # Forzar estado para que pase la guardia y re-llame al service.
    egreso_por_reembolsar.estado_pago = "por_reembolsar"
    egreso_por_reembolsar.save(update_fields=["estado_pago", "actualizado_en"])
    reembolsar_egreso(
        egreso_por_reembolsar,
        metodo="transferencia", banco_o_caja="banco",
        fecha=date.today(), actor=actor,
    )
    n_despues = Asiento.objects.filter(referencia_externa=ref).count()
    assert n_antes == n_despues == 1


# ── Views ────────────────────────────────────────────────────────────────


def test_get_htmx_devuelve_modal(client, egreso_por_reembolsar, usuario_factory):
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    url = reverse("tesoreria:egreso-reembolsar", args=[egreso_por_reembolsar.pk])
    resp = client.get(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Reembolsar egreso" in contenido
    assert egreso_por_reembolsar.codigo in contenido
    assert "Pagar reembolso" in contenido


def test_post_htmx_devuelve_204_hx_redirect(client, egreso_por_reembolsar,
                                             usuario_factory):
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    url = reverse("tesoreria:egreso-reembolsar", args=[egreso_por_reembolsar.pk])
    resp = client.post(
        url,
        data={
            "metodo": "transferencia",
            "banco_o_caja": "banco",
            "fecha": date.today().isoformat(),
        },
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect") == reverse("tesoreria:por-pagar")
    egreso_por_reembolsar.refresh_from_db()
    assert egreso_por_reembolsar.estado_pago == "pagado"
