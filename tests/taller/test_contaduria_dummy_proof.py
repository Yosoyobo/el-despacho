"""Tests del wizard dummy-proof de La Contaduría.

Cubre filtros direccion_partida + monto_partida, migración de cuenta
6.0.01 Ajustes de captura, vistas del wizard (selector, traspaso,
ajuste) y gating del botón "+ Asiento manual / Movimiento avanzado"
a super_admin.
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


# ── Filtros ──────────────────────────────────────────────────────────────

def test_filtro_direccion_partida(usuario_factory):
    """Cargo en deudora → Entra; Cargo en acreedora → Sale;
    Abono en deudora → Sale; Abono en acreedora → Entra."""
    from apps.contaduria import services
    from apps.contaduria.models import CuentaContable
    from apps.contaduria.templatetags.contaduria_helpers import direccion_partida

    u = usuario_factory(rol="dueno")
    asiento = services.crear_asiento(
        descripcion="Test direccion",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("100")},  # bancos (deudora) cargo → Entra
            {"cuenta": "4.1.01", "abono": Decimal("100")},  # ingresos (acreedora) abono → Entra
        ],
        creado_por=u,
    )
    bancos = CuentaContable.objects.get(codigo="1.1.02")
    ingresos = CuentaContable.objects.get(codigo="4.1.01")

    p_bancos = asiento.partidas.get(cuenta=bancos)
    p_ingresos = asiento.partidas.get(cuenta=ingresos)
    assert direccion_partida(p_bancos) == "Entra"
    assert direccion_partida(p_ingresos) == "Entra"

    # Caso opuesto
    asiento2 = services.crear_asiento(
        descripcion="Test direccion 2",
        partidas=[
            {"cuenta": "1.1.02", "abono": Decimal("50")},  # bancos abono → Sale
            {"cuenta": "5.1.01", "cargo": Decimal("50")},  # egreso (deudora) cargo → Entra
        ],
        creado_por=u,
    )
    p_bancos2 = asiento2.partidas.filter(cuenta=bancos).first()
    p_egreso = asiento2.partidas.filter(cuenta__codigo="5.1.01").first()
    assert direccion_partida(p_bancos2) == "Sale"
    assert direccion_partida(p_egreso) == "Entra"


def test_filtro_monto_partida(usuario_factory):
    from apps.contaduria import services
    from apps.contaduria.templatetags.contaduria_helpers import monto_partida

    u = usuario_factory(rol="dueno")
    asiento = services.crear_asiento(
        descripcion="Test monto",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("250.00")},
            {"cuenta": "4.1.01", "abono": Decimal("250.00")},
        ],
        creado_por=u,
    )
    p_cargo = asiento.partidas.filter(cargo__gt=0).first()
    p_abono = asiento.partidas.filter(abono__gt=0).first()
    assert monto_partida(p_cargo) == Decimal("250.00")
    assert monto_partida(p_abono) == Decimal("250.00")


# ── Migración cuenta de ajustes ──────────────────────────────────────────

def test_migracion_crea_cuenta_ajuste_captura():
    from apps.contaduria.models import CuentaContable
    c = CuentaContable.objects.filter(codigo="6.0.01").first()
    assert c is not None
    assert c.nombre == "Ajustes de captura"
    assert c.naturaleza == "acreedora"
    assert c.slot == "ajuste_captura"
    assert c.activa is True


# ── Wizard: pantalla 1 ───────────────────────────────────────────────────

def test_movimiento_nuevo_accesible(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    resp = client.get("/contaduria/movimiento/nuevo/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Traspaso entre cuentas" in contenido
    assert "Ajuste de saldo" in contenido


# ── Wizard: traspaso ─────────────────────────────────────────────────────

def test_traspaso_valido_genera_asiento(client, usuario_factory):
    from apps.contaduria.models import Asiento, CuentaContable

    u = usuario_factory(rol="contador")
    client.force_login(u)
    caja = CuentaContable.objects.get(codigo="1.1.01")  # caja
    bancos = CuentaContable.objects.get(codigo="1.1.02")  # bancos

    resp = client.post("/contaduria/movimiento/traspaso/", {
        "cuenta_origen": bancos.pk,
        "cuenta_destino": caja.pk,
        "monto": "500",
        "fecha": date.today().isoformat(),
        "descripcion": "Saqué efectivo del banco para caja chica",
    }, follow=False)
    assert resp.status_code == 302, resp.content.decode()[:500]

    # Asiento generado con D destino / H origen
    asiento = Asiento.objects.filter(descripcion__icontains="caja chica").first()
    assert asiento is not None
    p_destino = asiento.partidas.get(cuenta=caja)
    p_origen = asiento.partidas.get(cuenta=bancos)
    assert p_destino.cargo == Decimal("500.00")
    assert p_destino.abono == Decimal("0.00")
    assert p_origen.abono == Decimal("500.00")
    assert p_origen.cargo == Decimal("0.00")
    # Redirect al detalle del asiento
    assert resp["Location"].endswith(f"/contaduria/asientos/{asiento.pk}/")


# ── Wizard: ajuste ───────────────────────────────────────────────────────

def test_ajuste_sube_cuenta_deudora(client, usuario_factory):
    from apps.contaduria.models import Asiento, CuentaContable

    u = usuario_factory(rol="contador")
    client.force_login(u)
    caja = CuentaContable.objects.get(codigo="1.1.01")  # deudora
    ajuste = CuentaContable.objects.get(codigo="6.0.01")  # acreedora

    resp = client.post("/contaduria/movimiento/ajuste/", {
        "cuenta": caja.pk,
        "direccion": "sube",
        "monto": "100",
        "fecha": date.today().isoformat(),
        "motivo": "Sobraban 100 al contar la caja",
    }, follow=False)
    assert resp.status_code == 302, resp.content.decode()[:500]

    asiento = Asiento.objects.filter(origen="ajuste", descripcion__icontains="Sobraban").first()
    assert asiento is not None
    # Sube deudora → D caja / H ajustes
    p_caja = asiento.partidas.get(cuenta=caja)
    p_ajuste = asiento.partidas.get(cuenta=ajuste)
    assert p_caja.cargo == Decimal("100.00")
    assert p_ajuste.abono == Decimal("100.00")


def test_ajuste_baja_cuenta_deudora(client, usuario_factory):
    from apps.contaduria.models import Asiento, CuentaContable

    u = usuario_factory(rol="contador")
    client.force_login(u)
    caja = CuentaContable.objects.get(codigo="1.1.01")  # deudora
    ajuste = CuentaContable.objects.get(codigo="6.0.01")  # acreedora

    resp = client.post("/contaduria/movimiento/ajuste/", {
        "cuenta": caja.pk,
        "direccion": "baja",
        "monto": "75",
        "fecha": date.today().isoformat(),
        "motivo": "Faltaron 75 al contar la caja",
    }, follow=False)
    assert resp.status_code == 302

    asiento = Asiento.objects.filter(origen="ajuste", descripcion__icontains="Faltaron").first()
    assert asiento is not None
    # Baja deudora → H caja / D ajustes
    p_caja = asiento.partidas.get(cuenta=caja)
    p_ajuste = asiento.partidas.get(cuenta=ajuste)
    assert p_caja.abono == Decimal("75.00")
    assert p_ajuste.cargo == Decimal("75.00")


def test_ajuste_sin_motivo_falla(client, usuario_factory):
    from apps.contaduria.models import Asiento, CuentaContable

    u = usuario_factory(rol="contador")
    client.force_login(u)
    caja = CuentaContable.objects.get(codigo="1.1.01")
    cuenta_antes = Asiento.objects.filter(origen="ajuste").count()

    resp = client.post("/contaduria/movimiento/ajuste/", {
        "cuenta": caja.pk,
        "direccion": "sube",
        "monto": "100",
        "fecha": date.today().isoformat(),
        "motivo": "",
    })
    # No redirect — re-render con error
    assert resp.status_code == 200
    assert Asiento.objects.filter(origen="ajuste").count() == cuenta_antes


# ── Gating del botón "+ Movimiento avanzado / Asiento manual" ────────────

def test_botones_landing_para_contador(client, usuario_factory):
    """Contador ve '+ Nuevo movimiento' pero NO '+ Movimiento avanzado'."""
    u = usuario_factory(rol="contador")
    client.force_login(u)
    resp = client.get("/contaduria/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "+ Nuevo movimiento" in html
    assert "+ Movimiento avanzado" not in html
    assert "+ Asiento manual" not in html


def test_botones_landing_para_super_admin(client, usuario_factory):
    """super_admin ve ambos: '+ Nuevo movimiento' y '+ Movimiento avanzado'."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/contaduria/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "+ Nuevo movimiento" in html
    assert "+ Movimiento avanzado" in html
