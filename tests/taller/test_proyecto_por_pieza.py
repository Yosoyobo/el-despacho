"""S-LC-Proyecto-V2 (Oscar 2026-06-16): procesos fijos vs por pieza.

- Impresión "por pieza" multiplica su costo por (cantidad + merma).
- `sincronizar_procesos` es idempotente y preserva el FK `egreso` (un gasto ya
  registrado no reaparece como pendiente).
- El gasto del producto refleja las piezas a PRODUCIR (cantidad + merma).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="PorPieza Test")
    serv = Servicio.objects.create(
        nombre="Playeras", categoria=cat,
        precio_base=Decimal("196.00"), costo=Decimal("145.00"), activo=True,
    )
    prov = Proveedor.objects.create(razon_social="Impresor SA", activo=True)
    return {"cat": cat, "serv": serv, "prov": prov}


def _producto(proyecto, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    defaults = dict(
        servicio=catalogo["serv"], cantidad=35, merma=10,
        precio_unitario=Decimal("196.00"), costo_unitario=Decimal("145.00"),
        incluir_en_calculo=True, proveedor=catalogo["prov"],
    )
    defaults.update(kw)
    return ProyectoProducto.objects.create(proyecto=proyecto, **defaults)


def test_impresion_por_pieza_multiplica(proyecto_factory, catalogo):
    """Impresión 47.75 × 45 pz (35 + 10 merma) = 2,148.75; producto 145 × 45 = 6,525."""
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("47.75"), por_pieza=True,
    )
    assert pp.costo_total_linea == Decimal("6525.00")        # 145 × 45
    assert pp.costo_procesos == Decimal("2148.75")           # 47.75 × 45
    assert pp.costo_total_con_procesos == Decimal("8673.75")  # cubre el ejemplo de Oscar


def test_proceso_fijo_no_multiplica(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Viáticos",
        costo=Decimal("200.00"), por_pieza=False,
    )
    assert pp.costo_procesos == Decimal("200.00")  # fijo, una vez


def test_deuda_por_proveedor_impresion_por_pieza(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo, proveedor=None)  # sin proveedor de producto
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("47.75"), por_pieza=True,
    )
    deuda = p.deuda_por_proveedor()
    assert len(deuda) == 1
    assert deuda[0]["total"] == Decimal("2148.75")  # 47.75 × 45, no 47.75


def test_gasto_label_refleja_produccion(proyecto_factory, catalogo):
    """El gasto del producto dice las piezas a producir (45), no la cantidad (35)."""
    from apps.los_proyectos import gastos
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    unidades = list(gastos.iter_unidades(p))
    prod = next(u for u in unidades if u["clase"] == "producto")
    assert "45 pz" in prod["label"]
    assert "35 + 10 merma" in prod["label"]


def test_gasto_proceso_por_pieza_monto(proyecto_factory, catalogo):
    from apps.los_proyectos import gastos
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("47.75"), por_pieza=True,
    )
    unidades = list(gastos.iter_unidades(p))
    proc = next(u for u in unidades if u["clase"] == "proceso")
    assert proc["monto"] == Decimal("2148.75")
    assert "× 45 pz" in proc["label"]


def test_egreso_impresion_por_pieza_monto(proyecto_factory, catalogo):
    """Al pasar a producción, el egreso de la impresión por pieza es 47.75 × 45."""
    from apps.los_proyectos.models import ProyectoProductoProceso
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("47.75"), por_pieza=True,
    )
    p.estado = "en_proceso_produccion"
    p.save()
    montos = sorted(float(e.monto) for e in Egreso.objects.filter(proyecto=p, origen="proyecto"))
    assert montos == [2148.75, 6525.0]


def test_sincronizar_preserva_egreso(proyecto_factory, catalogo):
    """Re-sincronizar (autosave) NO debe perder el FK egreso de un proceso ya
    registrado, ni recrear el proceso (cambia el pk)."""
    from apps.los_proyectos.models import ProyectoProductoProceso
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    from apps.tesoreria.models import CentroDeCosto, Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    proc = ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=catalogo["prov"],
        costo=Decimal("47.75"), por_pieza=True,
    )
    from datetime import date
    centro, _ = CentroDeCosto.objects.get_or_create(
        slug="insumos-de-proyecto", defaults={"nombre": "Insumos de proyecto"})
    eg = Egreso.objects.create(
        monto=Decimal("2148.75"), fecha=date.today(), descripcion="x",
        centro_de_costo=centro, proyecto=p, proveedor=catalogo["prov"],
    )
    proc.egreso = eg
    proc.save(update_fields=["egreso"])
    pk_original = proc.pk

    import json
    payload = json.dumps([
        {"tipo": "impresion", "proveedor_id": catalogo["prov"].pk, "costo": "47.75", "por_pieza": True},
    ])
    sincronizar_procesos(pp, payload)

    proc.refresh_from_db()
    assert proc.pk == pk_original          # no se recreó
    assert proc.egreso_id == eg.pk         # FK egreso preservado
    assert proc.por_pieza is True          # por_pieza persistido


def test_sincronizar_borra_sobrantes_y_persiste_por_pieza(proyecto_factory, catalogo):
    import json

    from apps.los_proyectos.models import ProyectoProductoProceso
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo)
    # Estado inicial: 2 operativos
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="A", costo=Decimal("10"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="B", costo=Decimal("20"))
    # Re-sincronizar con 1 operativo por_pieza
    sincronizar_procesos(pp, json.dumps([
        {"tipo": "operativo", "descripcion": "A", "costo": "10", "por_pieza": True},
    ]))
    procs = list(pp.procesos.all())
    assert len(procs) == 1
    assert procs[0].descripcion == "A"
    assert procs[0].por_pieza is True
