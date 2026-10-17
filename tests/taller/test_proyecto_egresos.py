"""Oscar 2026-10-14: los egresos de un proyecto NUNCA se generan solos.

Hasta 2026-10-13 un signal creaba un Egreso «pendiente» por línea al pasar el
proyecto a producción (B, 2026-06-07). Oscar lo retiró: «la lista de egresos debe
empezar vacía y sólo registrar lo que se registra». Lo que falta por pagar lo
sugiere la sección amarilla (`gastos.pagos_pendientes_de`); un egreso sólo existe
si alguien lo registra a mano. Estos tests blindan que NADA lo vuelva a crear solo.
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


def _pasar_a_produccion(p):
    p.estado = "en_proceso_produccion"
    p.save()


def test_transicion_a_produccion_no_genera_egresos(proyecto_factory, catalogo):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)  # 40 * 2 = 80
    _producto(p, catalogo, cantidad=1, costo_unitario=Decimal("10.00"))  # 10
    _pasar_a_produccion(p)
    assert Egreso.objects.filter(proyecto=p).count() == 0
    # ni ida y vuelta, ni guardados posteriores
    p.estado = "en_proceso_diseno"
    p.save()
    _pasar_a_produccion(p)
    p.save()
    assert Egreso.objects.filter(proyecto=p).count() == 0


def test_no_genera_asiento_contable_solo(proyecto_factory, catalogo):
    from apps.contaduria.models import Asiento
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    _pasar_a_produccion(p)
    assert not Asiento.objects.filter(origen="auto_egreso").exists()


def test_lo_que_falta_sale_como_pago_pendiente(proyecto_factory, catalogo):
    """La sugerencia (sección amarilla) sigue viva sin crear ningún egreso."""
    from apps.los_proyectos import gastos
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)
    _pasar_a_produccion(p)
    pend = gastos.pagos_pendientes_de(p)
    assert [float(u["monto"]) for u in pend] == [80.0]


def test_registrar_a_mano_si_crea_el_egreso_con_su_autor(proyecto_factory, catalogo, usuario_factory):
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import Egreso
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_produccion")
    pp = _producto(p, catalogo)
    eg = gastos.registrar_egreso(p, "producto", pp.pk, actor=u, estado_pago="pagado")
    assert eg is not None and eg.creado_por_id == u.pk
    assert Egreso.objects.filter(proyecto=p, origen="proyecto").count() == 1
    assert gastos.pagos_pendientes_de(p) == []


def test_ningun_egreso_aparece_en_el_detalle_del_proyecto(proyecto_factory, catalogo, usuario_factory):
    from apps.el_dictado.herramientas import _h_detalle_proyecto
    p = proyecto_factory(estado="en_proceso_diseno")
    _producto(p, catalogo)  # costo 80
    _pasar_a_produccion(p)
    u = usuario_factory(rol="super_admin")
    out = _h_detalle_proyecto({"proyecto_slug": p.codigo}, u)
    assert out["costo_produccion"] == 80.0
    assert out["egresos_registrados"]["cantidad"] == 0
    assert any(d["proveedor"] == "Impresos SA" for d in out["deuda_por_proveedor"])
