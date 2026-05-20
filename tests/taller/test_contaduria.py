"""Tests de La Contaduría V1 (S3.contaduria-v1).

Cubre:
- Seed catálogo (cuentas existen tras migrate).
- Partida doble: crear_asiento valida cuadre, rechaza desbalance.
- Idempotencia por referencia_externa.
- Hookpoints automáticos: Ingreso/Egreso de Tesorería generan asientos.
- Anulación de Ingreso/Egreso genera asiento reverso.
- Permisos por rol.
- Vistas: landing, cuentas, asientos, detalle, balance, libro mayor, anular HTMX.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """En tests con db fixture, transaction.on_commit no se dispara porque la
    tx hace rollback. Forzamos ejecución inmediata para validar signals."""
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit",
        lambda fn, using=None, robust=False: fn(),
    )


@pytest.fixture
def centro_basico():
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.create(
        nombre="General", slug="general", naturaleza="operativo", activo=True,
    )


# ── Seed ─────────────────────────────────────────────────────────────────

def test_seed_cuentas_cargado():
    from apps.contaduria.models import CuentaContable
    assert CuentaContable.objects.count() >= 20
    # Cuentas con slot crítico deben existir
    for slot in ("caja", "banco", "cxc", "cxp", "reembolsos",
                 "ingreso_ventas", "egreso_operativo"):
        assert CuentaContable.objects.filter(slot=slot, activa=True).exists(), f"falta slot {slot}"


# ── Partida doble ────────────────────────────────────────────────────────

def test_crear_asiento_partida_doble_valida(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    asiento = services.crear_asiento(
        descripcion="Test manual",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("1000.00")},
            {"cuenta": "4.1.01", "abono": Decimal("1000.00")},
        ],
        creado_por=u,
    )
    assert asiento.codigo.startswith(f"AST-{date.today().year}-")
    assert asiento.partidas.count() == 2


def test_crear_asiento_desbalanceado_falla(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    with pytest.raises(services.AsientoInvalido):
        services.crear_asiento(
            descripcion="Mal cuadrado",
            partidas=[
                {"cuenta": "1.1.02", "cargo": Decimal("1000.00")},
                {"cuenta": "4.1.01", "abono": Decimal("500.00")},
            ],
            creado_por=u,
        )


def test_partida_con_cargo_y_abono_falla(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    with pytest.raises(services.AsientoInvalido):
        services.crear_asiento(
            descripcion="Partida ambigua",
            partidas=[
                {"cuenta": "1.1.02", "cargo": Decimal("100"), "abono": Decimal("100")},
                {"cuenta": "4.1.01", "abono": Decimal("100")},
            ],
            creado_por=u,
        )


def test_asiento_requiere_minimo_2_partidas(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    with pytest.raises(services.AsientoInvalido):
        services.crear_asiento(
            descripcion="Una sola",
            partidas=[{"cuenta": "1.1.02", "cargo": Decimal("100")}],
            creado_por=u,
        )


def test_cuenta_inexistente_falla(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    with pytest.raises(services.AsientoInvalido):
        services.crear_asiento(
            descripcion="Cuenta fake",
            partidas=[
                {"cuenta": "9.9.99", "cargo": Decimal("100")},
                {"cuenta": "4.1.01", "abono": Decimal("100")},
            ],
            creado_por=u,
        )


# ── Idempotencia ─────────────────────────────────────────────────────────

def test_idempotencia_por_referencia(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    a1 = services.crear_asiento(
        descripcion="Primero",
        referencia_externa="test:42",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("500")},
            {"cuenta": "4.1.01", "abono": Decimal("500")},
        ],
        creado_por=u,
    )
    a2 = services.crear_asiento(
        descripcion="Repetido (no debe duplicar)",
        referencia_externa="test:42",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("500")},
            {"cuenta": "4.1.01", "abono": Decimal("500")},
        ],
        creado_por=u,
    )
    assert a1.pk == a2.pk


# ── Hookpoints automáticos Tesorería ─────────────────────────────────────

def test_ingreso_genera_asiento_automatico(usuario_factory, cliente_factory):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Ingreso

    u = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=u)
    ing = Ingreso.objects.create(
        monto=Decimal("1500.00"), fecha=date.today(),
        descripcion="Cobro mayo", cliente=cli, metodo="transferencia",
        creado_por=u,
    )
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"tesoreria.ingreso:{ing.pk}"
    ).first()
    assert asiento is not None
    assert asiento.origen == "auto_ingreso"
    cargos = sum(p.cargo for p in asiento.partidas.all())
    assert cargos == Decimal("1500.00")


def test_egreso_genera_asiento_automatico(usuario_factory, centro_basico):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Egreso

    u = usuario_factory(rol="super_admin")
    eg = Egreso.objects.create(
        monto=Decimal("800.00"), fecha=date.today(),
        descripcion="Luz", centro_de_costo=centro_basico,
        metodo="transferencia", estado_pago="pagado", creado_por=u,
    )
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"tesoreria.egreso:{eg.pk}"
    ).first()
    assert asiento is not None
    assert asiento.origen == "auto_egreso"


def test_egreso_reembolso_usa_cuenta_de_reembolsos(usuario_factory, centro_basico):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Egreso

    u = usuario_factory(rol="super_admin")
    eg = Egreso.objects.create(
        monto=Decimal("200.00"), fecha=date.today(),
        descripcion="Café del equipo", centro_de_costo=centro_basico,
        metodo="tarjeta_personal", estado_pago="por_reembolsar",
        pagado_por=u, creado_por=u,
    )
    asiento = Asiento.vigentes.filter(
        referencia_externa=f"tesoreria.egreso:{eg.pk}"
    ).first()
    assert asiento is not None
    # La cuenta de abono debe ser slot 'reembolsos' (2.1.03)
    abono_partida = asiento.partidas.filter(abono__gt=0).first()
    assert abono_partida.cuenta.slot == "reembolsos"


def test_anular_ingreso_genera_asiento_reverso(usuario_factory, cliente_factory):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Ingreso
    from django.utils import timezone

    u = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=u)
    ing = Ingreso.objects.create(
        monto=Decimal("300.00"), fecha=date.today(),
        descripcion="Cobro", cliente=cli, creado_por=u, metodo="transferencia",
    )
    ing.anulado = True
    ing.anulado_en = timezone.now()
    ing.save()
    reverso = Asiento.vigentes.filter(
        referencia_externa=f"tesoreria.ingreso.anulacion:{ing.pk}"
    ).first()
    assert reverso is not None
    assert reverso.origen == "auto_anulacion_ingreso"


# ── Saldos ───────────────────────────────────────────────────────────────

def test_saldo_cuenta_caja_y_balance(usuario_factory):
    from apps.contaduria import services
    from apps.contaduria.models import CuentaContable

    u = usuario_factory(rol="dueno")
    services.crear_asiento(
        descripcion="Aporte inicial",
        partidas=[
            {"cuenta": "1.1.01", "cargo": Decimal("5000")},
            {"cuenta": "3.1.01", "abono": Decimal("5000")},
        ],
        creado_por=u,
    )
    caja = CuentaContable.objects.get(slot="caja")
    assert services.saldo_cuenta(caja) == Decimal("5000.00")
    filas = services.balance_de_comprobacion()
    total_c = sum(f["cargos"] for f in filas)
    total_a = sum(f["abonos"] for f in filas)
    assert total_c == total_a


# ── Permisos / Vistas ────────────────────────────────────────────────────

def test_anonimo_redirige(client):
    resp = client.get("/contaduria/")
    assert resp.status_code in (301, 302)


def test_disenador_no_accede(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/contaduria/").status_code == 403


def test_contador_ve_landing(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    assert client.get("/contaduria/").status_code == 200


def test_admin_captura_asiento_via_view(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    from apps.contaduria.models import CuentaContable
    c1 = CuentaContable.objects.get(codigo="1.1.02")
    c2 = CuentaContable.objects.get(codigo="4.1.01")
    resp = client.post("/contaduria/asientos/nuevo/", {
        "fecha": date.today().isoformat(),
        "descripcion": "Captura manual de prueba",
        "referencia_externa": "",
        "partidas-TOTAL_FORMS": "2", "partidas-INITIAL_FORMS": "0",
        "partidas-MIN_NUM_FORMS": "0", "partidas-MAX_NUM_FORMS": "1000",
        "partidas-0-cuenta": c1.pk, "partidas-0-cargo": "100", "partidas-0-abono": "0",
        "partidas-0-orden": "0", "partidas-0-descripcion": "",
        "partidas-1-cuenta": c2.pk, "partidas-1-cargo": "0", "partidas-1-abono": "100",
        "partidas-1-orden": "1", "partidas-1-descripcion": "",
    }, follow=True)
    assert resp.status_code == 200
    from apps.contaduria.models import Asiento
    assert Asiento.objects.filter(descripcion="Captura manual de prueba").exists()


def test_balance_endpoint(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    resp = client.get("/contaduria/balance/")
    assert resp.status_code == 200


def test_libro_mayor_endpoint(client, usuario_factory):
    from apps.contaduria.models import CuentaContable
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    caja = CuentaContable.objects.get(slot="caja")
    resp = client.get(f"/contaduria/libro-mayor/{caja.pk}/")
    assert resp.status_code == 200


def test_anular_asiento_via_htmx(client, usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="super_admin")
    asiento = services.crear_asiento(
        descripcion="Para anular",
        partidas=[
            {"cuenta": "1.1.02", "cargo": Decimal("100")},
            {"cuenta": "4.1.01", "abono": Decimal("100")},
        ],
        creado_por=u,
    )
    client.force_login(u)
    resp = client.post(
        f"/contaduria/asientos/{asiento.pk}/anular/",
        {"motivo": "error de captura"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    asiento.refresh_from_db()
    assert asiento.anulado is True
