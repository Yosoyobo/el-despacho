"""Tests de La Contaduría V2 (S3.contaduria-v2).

Cubre:
- Estado de resultados: subgrupos, totales, utilidad, exclusión de anulados,
  filtro por rango.
- Balance general: ecuación contable, utilidad on-the-fly.
- Export CSV pólizas: encabezados, BOM, exclusión de anulados por default,
  flag para incluir, evento Portavoz.
- Export CSV catálogo.
- Vistas con permisos.
- KPI utilidad-neta-mes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit",
        lambda fn, using=None, robust=False: fn(),
    )


def _crear(descripcion, partidas, fecha=None, **kw):
    from apps.contaduria import services
    return services.crear_asiento(descripcion=descripcion, partidas=partidas, fecha=fecha, **kw)


# ── Estado de resultados ──────────────────────────────────────────────

def test_estado_resultados_suma_ingresos_y_egresos(usuario_factory):
    from apps.contaduria.reportes import estado_resultados
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    _crear("Venta", [
        {"cuenta": "1.1.02", "cargo": Decimal("1000")},
        {"cuenta": "4.1.01", "abono": Decimal("1000")},
    ], fecha=hoy, creado_por=u)
    _crear("Compra insumos", [
        {"cuenta": "5.1.02", "cargo": Decimal("300")},
        {"cuenta": "1.1.02", "abono": Decimal("300")},
    ], fecha=hoy, creado_por=u)
    _crear("Renta", [
        {"cuenta": "5.1.04", "cargo": Decimal("200")},
        {"cuenta": "1.1.02", "abono": Decimal("200")},
    ], fecha=hoy, creado_por=u)

    pl = estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    assert pl["ingresos"]["total"] == Decimal("1000.00")
    assert pl["total_costo_ventas"] == Decimal("300.00")
    assert pl["total_gastos_operativos"] == Decimal("200.00")
    assert pl["utilidad_bruta"] == Decimal("700.00")
    assert pl["utilidad_operativa"] == Decimal("500.00")
    assert pl["utilidad_neta"] == pl["utilidad_operativa"]


def test_estado_resultados_excluye_anulados(usuario_factory):
    from apps.contaduria import services
    from apps.contaduria.reportes import estado_resultados
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    a = services.crear_asiento(descripcion="Venta", partidas=[
        {"cuenta": "1.1.02", "cargo": Decimal("500")},
        {"cuenta": "4.1.01", "abono": Decimal("500")},
    ], creado_por=u)
    services.anular_asiento(a, actor=u, motivo="prueba")
    pl = estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    assert pl["ingresos"]["total"] == Decimal("0.00")


def test_estado_resultados_respeta_rango(usuario_factory):
    from apps.contaduria.reportes import estado_resultados
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    hace = hoy - timedelta(days=120)
    _crear("Venta vieja", [
        {"cuenta": "1.1.02", "cargo": Decimal("999")},
        {"cuenta": "4.1.01", "abono": Decimal("999")},
    ], fecha=hace, creado_por=u)
    _crear("Venta nueva", [
        {"cuenta": "1.1.02", "cargo": Decimal("100")},
        {"cuenta": "4.1.01", "abono": Decimal("100")},
    ], fecha=hoy, creado_por=u)
    pl = estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    assert pl["ingresos"]["total"] == Decimal("100.00")


def test_estado_resultados_agrupa_subgrupos(usuario_factory):
    from apps.contaduria.reportes import estado_resultados
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    _crear("Insumos", [
        {"cuenta": "5.1.02", "cargo": Decimal("100")},
        {"cuenta": "1.1.02", "abono": Decimal("100")},
    ], fecha=hoy, creado_por=u)
    _crear("Externos", [
        {"cuenta": "5.1.03", "cargo": Decimal("50")},
        {"cuenta": "1.1.02", "abono": Decimal("50")},
    ], fecha=hoy, creado_por=u)
    _crear("Renta", [
        {"cuenta": "5.1.04", "cargo": Decimal("200")},
        {"cuenta": "1.1.02", "abono": Decimal("200")},
    ], fecha=hoy, creado_por=u)

    pl = estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    claves = {sg["clave"]: sg["total"] for sg in pl["egresos"]["subgrupos"]}
    assert claves["costo_ventas"] == Decimal("150.00")  # 100 + 50
    assert claves["gastos_operativos"] == Decimal("200.00")


# ── Balance general ───────────────────────────────────────────────────

def test_balance_general_cumple_ecuacion_contable(usuario_factory):
    from apps.contaduria.reportes import balance_general
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    # Aportación de capital + venta + gasto
    _crear("Aportación socios", [
        {"cuenta": "1.1.02", "cargo": Decimal("10000")},
        {"cuenta": "3.1.01", "abono": Decimal("10000")},
    ], fecha=hoy, creado_por=u)
    _crear("Venta", [
        {"cuenta": "1.1.02", "cargo": Decimal("2000")},
        {"cuenta": "4.1.01", "abono": Decimal("2000")},
    ], fecha=hoy, creado_por=u)
    _crear("Renta", [
        {"cuenta": "5.1.04", "cargo": Decimal("500")},
        {"cuenta": "1.1.02", "abono": Decimal("500")},
    ], fecha=hoy, creado_por=u)

    bg = balance_general(hasta=hoy)
    # Activo = banco (10000 + 2000 - 500) = 11500
    assert bg["total_activo"] == Decimal("11500.00")
    # Capital = 10000, utilidad periodo = 2000 - 500 = 1500
    assert bg["total_capital"] == Decimal("10000.00")
    assert bg["utilidad_periodo"] == Decimal("1500.00")
    assert bg["cuadrado"] is True
    assert bg["descuadre"] == Decimal("0.00")


def test_balance_general_a_fecha_pasada(usuario_factory):
    from apps.contaduria.reportes import balance_general
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    _crear("Venta ayer", [
        {"cuenta": "1.1.02", "cargo": Decimal("500")},
        {"cuenta": "4.1.01", "abono": Decimal("500")},
    ], fecha=ayer, creado_por=u)
    _crear("Venta hoy", [
        {"cuenta": "1.1.02", "cargo": Decimal("700")},
        {"cuenta": "4.1.01", "abono": Decimal("700")},
    ], fecha=hoy, creado_por=u)
    bg_ayer = balance_general(hasta=ayer)
    bg_hoy = balance_general(hasta=hoy)
    assert bg_ayer["total_activo"] == Decimal("500.00")
    assert bg_hoy["total_activo"] == Decimal("1200.00")


# ── Export pólizas ────────────────────────────────────────────────────

def test_export_polizas_filas_y_encabezados(usuario_factory):
    from apps.contaduria import exports
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    _crear("Venta", [
        {"cuenta": "1.1.02", "cargo": Decimal("1000")},
        {"cuenta": "4.1.01", "abono": Decimal("1000")},
    ], fecha=hoy, creado_por=u)
    encabezados, filas = exports.filas_para("polizas", {"desde": hoy.isoformat(), "hasta": hoy.isoformat()})
    assert "Cargo" in encabezados and "Abono" in encabezados
    assert len(filas) == 2  # dos partidas


def test_export_polizas_excluye_anulados_por_default(usuario_factory):
    from apps.contaduria import exports, services
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    a = services.crear_asiento(descripcion="V", partidas=[
        {"cuenta": "1.1.02", "cargo": Decimal("100")},
        {"cuenta": "4.1.01", "abono": Decimal("100")},
    ], creado_por=u)
    services.anular_asiento(a, actor=u, motivo="x")
    _, filas = exports.filas_para("polizas", {"desde": hoy.isoformat(), "hasta": hoy.isoformat()})
    assert len(filas) == 0
    _, filas_con = exports.filas_para("polizas", {
        "desde": hoy.isoformat(), "hasta": hoy.isoformat(), "incluir_anulados": "1",
    })
    assert len(filas_con) == 2


def test_export_csv_response_tiene_bom(usuario_factory, rf):
    from apps.contaduria.exports import responder_csv
    u = usuario_factory(rol="dueno")
    response = responder_csv("catalogo", {}, actor=u)
    contenido = response.content
    # BOM "﻿" en UTF-8 son los bytes EF BB BF
    assert contenido[:3] == b"\xef\xbb\xbf"
    assert response["Content-Type"].startswith("text/csv")


def test_export_catalogo_lista_cuentas(usuario_factory):
    from apps.contaduria import exports
    encabezados, filas = exports.filas_para("catalogo", {})
    assert encabezados[0] == "Código"
    assert len(filas) >= 20
    # Cuenta 1.1.01 (Caja) debe estar
    assert any(f[0] == "1.1.01" for f in filas)


def test_export_polizas_emite_evento_portavoz(usuario_factory, monkeypatch):
    from apps.contaduria import exports
    u = usuario_factory(rol="dueno")
    eventos: list = []
    monkeypatch.setattr("apps.contaduria.exports.emitir", lambda e: eventos.append(e))
    exports.responder_csv("polizas", {}, actor=u)
    assert any(e.tipo == "contaduria.exportado" for e in eventos)


# ── Vistas con permisos ───────────────────────────────────────────────

def test_estado_resultados_requiere_permiso_reportes(usuario_factory, client):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get(reverse("contaduria:estado-resultados"))
    assert resp.status_code == 403


def test_estado_resultados_admin_render(usuario_factory, client):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get(reverse("contaduria:estado-resultados"))
    assert resp.status_code == 200
    assert b"Estado de resultados" in resp.content


def test_balance_general_render(usuario_factory, client):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get(reverse("contaduria:balance-general"))
    assert resp.status_code == 200
    assert b"Balance general" in resp.content


def test_export_descarga_csv(usuario_factory, client):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get(reverse("contaduria:export") + "?descargar=1&formato=catalogo")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "attachment" in resp["Content-Disposition"]


# ── KPI ────────────────────────────────────────────────────────────────

def test_kpi_utilidad_neta_mes(usuario_factory):
    from apps.taller_home.kpis import KPIS
    u = usuario_factory(rol="dueno")
    hoy = date.today()
    _crear("Venta", [
        {"cuenta": "1.1.02", "cargo": Decimal("800")},
        {"cuenta": "4.1.01", "abono": Decimal("800")},
    ], fecha=hoy, creado_por=u)
    _crear("Renta", [
        {"cuenta": "5.1.04", "cargo": Decimal("300")},
        {"cuenta": "1.1.02", "abono": Decimal("300")},
    ], fecha=hoy, creado_por=u)
    kpi = next(k for k in KPIS if k.slug == "contaduria-utilidad-neta-mes")
    resultado = kpi.calcular(u)
    assert "500" in resultado["valor"]
