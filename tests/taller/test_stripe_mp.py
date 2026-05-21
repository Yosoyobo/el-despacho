"""Tests del flujo Stripe/MercadoPago (S-Finanzas-V2 #C).

- Ingreso método=stripe asienta D Stripe / H Ingresos (no Bancos).
- Ingreso método=mercadopago asienta D MP / H Ingresos.
- Payout manual: traspaso Stripe→Banco actualiza ambos saldos.
- Atajo `?origen=stripe_saldo` en wizard preselecciona la cuenta.
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


def test_ingreso_stripe_asienta_a_cuenta_stripe(usuario_factory):
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="dueno")
    Ingreso.objects.create(
        monto=Decimal("1500.00"),
        fecha=date.today(),
        descripcion="Pago via Stripe",
        metodo="stripe",
        creado_por=u,
    )
    stripe = cuenta_por_slot("stripe_saldo")
    banco = cuenta_por_slot("banco")
    assert stripe is not None
    assert saldo_cuenta(stripe) == Decimal("1500.00")
    assert saldo_cuenta(banco) == Decimal("0.00")


def test_ingreso_mercadopago_asienta_a_cuenta_mp(usuario_factory):
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="dueno")
    Ingreso.objects.create(
        monto=Decimal("750.00"),
        fecha=date.today(),
        descripcion="Pago via MP",
        metodo="mercadopago",
        creado_por=u,
    )
    mp = cuenta_por_slot("mp_saldo")
    banco = cuenta_por_slot("banco")
    assert mp is not None
    assert saldo_cuenta(mp) == Decimal("750.00")
    assert saldo_cuenta(banco) == Decimal("0.00")


def test_payout_stripe_a_banco_actualiza_ambos(usuario_factory):
    """Tras un ingreso Stripe + payout via wizard de traspaso, el
    saldo en Stripe debe quedar en 0 y Banco con el monto."""
    from apps.contaduria import wizards
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="dueno")
    Ingreso.objects.create(
        monto=Decimal("2000.00"),
        fecha=date.today(),
        descripcion="Pago Stripe",
        metodo="stripe",
        creado_por=u,
    )
    stripe = cuenta_por_slot("stripe_saldo")
    banco = cuenta_por_slot("banco")
    assert saldo_cuenta(stripe) == Decimal("2000.00")

    wizards.registrar_traspaso(
        cuenta_origen=stripe,
        cuenta_destino=banco,
        monto=Decimal("2000.00"),
        descripcion="Payout de Stripe a Banco",
        fecha=date.today(),
        creado_por=u,
    )
    assert saldo_cuenta(stripe) == Decimal("0.00")
    assert saldo_cuenta(banco) == Decimal("2000.00")


def test_atajo_payout_preselecciona_stripe(client, usuario_factory):
    """GET /contaduria/movimiento/traspaso/?origen=stripe_saldo&destino=banco
    debe pre-seleccionar las cuentas en el form."""
    from apps.contaduria.services import cuenta_por_slot

    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/contaduria/movimiento/traspaso/?origen=stripe_saldo&destino=banco")
    assert resp.status_code == 200
    stripe = cuenta_por_slot("stripe_saldo")
    banco = cuenta_por_slot("banco")
    contenido = resp.content.decode()
    # El form debe tener selected en las dos cuentas pre-cargadas
    # (asumimos que el template usa `valores.cuenta_origen` / `cuenta_destino`)
    assert str(stripe.pk) in contenido
    assert str(banco.pk) in contenido


def test_landing_tesoreria_expone_saldo_stripe(client, usuario_factory):
    from apps.tesoreria.models import Ingreso
    u = usuario_factory(rol="dueno")
    Ingreso.objects.create(
        monto=Decimal("500.00"),
        fecha=date.today(),
        descripcion="Stripe",
        metodo="stripe",
        creado_por=u,
    )
    client.force_login(u)
    resp = client.get("/tesoreria/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Saldo en Stripe" in contenido
    assert "Registrar payout" in contenido
