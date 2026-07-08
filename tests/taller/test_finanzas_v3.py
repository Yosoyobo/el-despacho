"""S-Finanzas-V3 — Configuración Fiscal por GUI (RESICO/ISR/IVA),
gastos de proyecto no registrados → egresos, e IVA en el monto de proveedor.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _config(**kw):
    from ajustes.models import ConfiguracionFiscal
    cfg = ConfiguracionFiscal.obtener()
    for k, v in kw.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


def _asiento(cuenta_cargo, cuenta_abono, monto, fecha):
    from apps.contaduria import services
    return services.crear_asiento(
        descripcion="t", fecha=fecha, origen="manual",
        partidas=[{"cuenta": cuenta_cargo, "cargo": Decimal(monto)},
                  {"cuenta": cuenta_abono, "abono": Decimal(monto)}],
    )


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat V3")
    serv = Servicio.objects.create(
        nombre="Lanyards", categoria=cat,
        precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True)
    prov = Proveedor.objects.create(razon_social="Cintas SA", activo=True)
    return {"cat": cat, "serv": serv, "prov": prov}


# ── F1: Configuración Fiscal ──────────────────────────────────────────────

def test_default_resico_pf_isr_sobre_ingresos():
    from apps.contaduria import reportes
    hoy = date.today()
    _config(regimen="resico_pf", isr_base="ingresos", isr_tasa=Decimal("2.000"),
            ptu_aplica=False)
    _asiento("1.1.02", "4.1.01", "1000.00", hoy)
    _asiento("5.1.01", "1.1.02", "400.00", hoy)
    pl = reportes.estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    assert pl["isr_base"] == "ingresos"
    assert pl["isr_estimado"] == Decimal("20.00")   # 2% de 1000 (ingresos)
    assert pl["ptu_estimado"] == Decimal("0.00")    # PTU apagado


def test_regimen_general_isr_sobre_utilidad():
    from apps.contaduria import reportes
    hoy = date.today()
    _config(regimen="general_pm", isr_base="utilidad", isr_tasa=Decimal("30.000"),
            ptu_aplica=True, ptu_tasa=Decimal("10.000"))
    _asiento("1.1.02", "4.1.01", "1000.00", hoy)
    _asiento("5.1.01", "1.1.02", "400.00", hoy)
    pl = reportes.estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    assert pl["isr_estimado"] == Decimal("180.00")  # 30% de 600 (utilidad)
    assert pl["ptu_estimado"] == Decimal("60.00")   # 10% de 600


def test_proyecto_iva_lee_config(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory(estado="por_cotizar")
    ProyectoProducto.objects.create(
        proyecto=p, servicio=catalogo["serv"], cantidad=1,
        precio_unitario=Decimal("1000.00"), incluir_en_calculo=True)
    _config(iva_tasa=Decimal("16.000"))
    assert p.iva_monto == Decimal("160.00")
    _config(iva_tasa=Decimal("8.000"))
    assert p.iva_monto == Decimal("80.00")
    assert p.iva_pct_label == "8%"


# ── F2: gastos de proyecto no registrados ─────────────────────────────────

def _producto(p, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    d = dict(servicio=catalogo["serv"], cantidad=1,
             precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
             incluir_en_calculo=True, proveedor=catalogo["prov"])
    d.update(kw)
    return ProyectoProducto.objects.create(proyecto=p, **d)


def test_unidades_y_pendientes(proyecto_factory, catalogo):
    from apps.los_proyectos import gastos
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)  # costo_total_linea = 40
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Clavos", costo=Decimal("150.00"))
    unidades = list(gastos.iter_unidades(p))
    assert len(unidades) == 2  # producto + proceso
    assert all(not u["registrado"] for u in unidades)
    pend = gastos.pendientes_de(p)
    assert {u["tipo"] for u in pend} == {"producto", "operativo"}


def test_registrar_gasto_individual(proyecto_factory, catalogo):
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    eg = gastos.registrar_egreso(p, "producto", pp.pk, actor=None)
    assert eg is not None and float(eg.monto) == 40.0
    pp.refresh_from_db()
    assert pp.egreso_id == eg.pk
    # Idempotente: segunda llamada devuelve el mismo egreso.
    eg2 = gastos.registrar_egreso(p, "producto", pp.pk, actor=None)
    assert eg2.pk == eg.pk
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 1


def test_registrar_pendientes_y_conteo(proyecto_factory, catalogo):
    from apps.los_proyectos import gastos
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Clavos", costo=Decimal("150.00"))
    antes = gastos.conteo_no_registrados()
    assert antes["cantidad"] >= 2
    creados = gastos.registrar_pendientes(p, actor=None)
    assert len(creados) == 2
    assert gastos.pendientes_de(p) == []


def test_alerta_en_detalle_proyecto(client, usuario_factory, proyecto_factory, catalogo):
    # LC 2026-07: la alerta de "pagos pendientes sin registrar" sale de
    # PRODUCCIÓN en adelante, dentro del recuadro de egresos.
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(estado="en_proceso_produccion")
    _producto(p, catalogo)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "pendiente" in cuerpo and "sin registrar" in cuerpo


def test_registrar_gasto_via_view(client, usuario_factory, proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    resp = client.post(f"/proyectos/{p.pk}/gasto/producto/{pp.pk}/registrar")
    assert resp.status_code in (302, 200)
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 1


def test_tesoreria_gastos_no_registrados_page(client, usuario_factory, proyecto_factory, catalogo):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    resp = client.get("/tesoreria/gastos-no-registrados/")
    assert resp.status_code == 200
    assert p.codigo in resp.content.decode()


# ── F3: IVA en el cuadro de proveedores ───────────────────────────────────

def test_proveedores_panel_con_iva(proyecto_factory, catalogo):
    from apps.los_proyectos.views import _proveedores_panel
    _config(iva_tasa=Decimal("16.000"))
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo, costo_unitario=Decimal("5600.00"), cantidad=1)
    filas = _proveedores_panel(p)
    assert len(filas) == 1
    fila = filas[0]
    assert fila["total"] == Decimal("5600.00")
    assert fila["iva"] == Decimal("896.00")          # 16% de 5600
    assert fila["total_con_iva"] == Decimal("6496.00")
