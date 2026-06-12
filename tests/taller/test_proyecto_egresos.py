"""B (2026-06-07): al pasar un proyecto a producción se generan Egresos.

Un Egreso por línea de producto incluida con costo > 0. Idempotente. Alimenta
Tesorería + el asiento auto_egreso de Contaduría, y la herramienta
`detalle_proyecto` del Chalán surfacea costos/egresos/deuda.
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
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Prod Egreso Test")
    serv = Servicio.objects.create(
        nombre="Vasos PET", categoria=cat,
        precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True,
    )
    prov = Proveedor.objects.create(razon_social="Impresos SA", activo=True)
    return {"cat": cat, "serv": serv, "prov": prov}


def _producto(proyecto, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    defaults = dict(
        servicio=catalogo["serv"], cantidad=2,
        precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
        incluir_en_calculo=True, proveedor=catalogo["prov"],
    )
    defaults.update(kw)
    return ProyectoProducto.objects.create(proyecto=proyecto, **defaults)


def test_transicion_genera_egreso_por_linea(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)  # 40 * 2 = 80
    _producto(p, catalogo, cantidad=1, costo_unitario=Decimal("10.00"))  # 10
    p.estado = "en_proceso_produccion"
    p.save()
    egresos = Egreso.objects.filter(proyecto=p, origen="proyecto")
    assert egresos.count() == 2
    assert sorted(float(e.monto) for e in egresos) == [10.0, 80.0]
    e = egresos.order_by("monto").last()
    assert e.centro_de_costo.slug == "insumos-de-proyecto"
    assert e.estado_pago == "pendiente"
    assert e.proveedor_id == catalogo["prov"].id


def test_idempotente_no_duplica(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    p.estado = "en_proceso_produccion"
    p.save()
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 1
    # Volver a diseño y de nuevo a producción no duplica (la línea ya tiene egreso).
    p.estado = "en_proceso_diseno"
    p.save()
    p.estado = "en_proceso_produccion"
    p.save()
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 1


def test_linea_excluida_no_genera(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo, incluir_en_calculo=False)
    p.estado = "en_proceso_produccion"
    p.save()
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 0


def test_costo_cero_no_genera(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo, costo_unitario=Decimal("0.00"))
    p.estado = "en_proceso_produccion"
    p.save()
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 0


def test_gasto_por_separado_producto_y_proceso(proyecto_factory, catalogo):
    """S-Finanzas-V3 (decisión Oscar 2026-06-12): cada gasto liga su PROPIO
    egreso — el producto (costo de línea) y cada proceso operativo por separado."""
    from apps.los_proyectos.models import ProyectoProductoProceso
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    pp = _producto(p, catalogo, cantidad=1, costo_unitario=Decimal("40.00"))
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Clavos", costo=Decimal("30.00"),
    )
    p.estado = "en_proceso_produccion"
    p.save()
    egresos = Egreso.objects.filter(proyecto=p, origen="proyecto")
    assert egresos.count() == 2  # producto (40) + proceso "Clavos" (30) por separado
    assert sorted(float(e.monto) for e in egresos) == [30.0, 40.0]


def test_egreso_genera_asiento_contable(proyecto_factory, catalogo):
    from apps.contaduria.models import Asiento
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    p.estado = "en_proceso_produccion"
    p.save()
    assert Asiento.objects.filter(origen="auto_egreso").exists()


def test_no_genera_al_crear_en_diseno(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 0


def test_detalle_proyecto_surfacea_costos_y_egresos(proyecto_factory, catalogo, usuario_factory):
    from apps.el_dictado.herramientas import _h_detalle_proyecto
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)  # costo 80
    p.estado = "en_proceso_produccion"
    p.save()
    u = usuario_factory(rol="super_admin")
    out = _h_detalle_proyecto({"proyecto_slug": p.codigo}, u)
    assert out["costo_produccion"] == 80.0
    assert out["egresos_registrados"]["cantidad"] == 1
    assert out["egresos_registrados"]["total"] == 80.0
    assert any(d["proveedor"] == "Impresos SA" for d in out["deuda_por_proveedor"])
