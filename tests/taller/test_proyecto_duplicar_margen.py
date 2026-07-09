"""Fase 3 (LC 2026-07) — margen % y duplicar proyecto."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _servicio(nombre="Playera", precio="100", costo="40"):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Prod")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal(precio), costo=Decimal(costo), activo=True,
    )


def _linea(proy, serv, *, cantidad=10, merma=0, precio=None, costo=None, prov=None):
    from apps.los_proyectos.models import ProyectoProducto
    return ProyectoProducto.objects.create(
        proyecto=proy, servicio=serv, cantidad=cantidad, merma=merma,
        precio_unitario=Decimal(precio) if precio else None,
        costo_unitario=Decimal(costo) if costo else None,
        proveedor=prov,
    )


def test_margen_producto_resta_merma(cliente_factory, usuario_factory):
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="P", cliente=cli, creado_por=autor)
    serv = _servicio(precio="100", costo="40")
    # 10 piezas vendidas a 100 = 1000; costo 40 × (10+2 merma) = 480; util=520; margen=52%
    pp = _linea(proy, serv, cantidad=10, merma=2)
    assert pp.subtotal == Decimal("1000.00")
    assert pp.costo_total_linea == Decimal("480.00")
    assert pp.utilidad == Decimal("520.00")
    assert pp.margen_porcentaje == Decimal("52.0")


def test_margen_proyecto(cliente_factory, usuario_factory):
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="P", cliente=cli, creado_por=autor)
    _linea(proy, _servicio(precio="100", costo="40"), cantidad=10)
    assert proy.margen_porcentaje == Decimal("60.0")


def test_duplicar_copia_productos_y_procesos(cliente_factory, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import Proyecto
    from apps.los_proyectos.models.proceso import ProyectoProductoProceso
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    prov = Proveedor.objects.create(razon_social="Tela SA", activo=True)
    proy = Proyecto.objects.create(
        nombre="Original", cliente=cli, regimen_fiscal="honorarios",
        monto_cobrado=Decimal("500"), creado_por=autor,
    )
    serv = _servicio()
    pp = _linea(proy, serv, cantidad=5, precio="120", costo="50", prov=prov)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=prov, costo=Decimal("15"), por_pieza=True,
    )

    nuevo = duplicar_proyecto(proy, nombre="Clon", actor=autor)
    assert nuevo.pk != proy.pk
    assert nuevo.nombre == "Clon"
    assert nuevo.cliente_id == cli.pk
    assert nuevo.regimen_fiscal == "honorarios"
    # Dinero NO se hereda.
    assert nuevo.monto_cobrado == Decimal("0")
    assert nuevo.estado == "por_cotizar"
    # Productos + procesos copiados con proveedor/costo/precio.
    lineas = list(nuevo.productos.all())
    assert len(lineas) == 1
    l = lineas[0]
    assert l.servicio_id == serv.pk
    assert l.proveedor_id == prov.pk
    assert l.precio_unitario == Decimal("120")
    assert l.costo_unitario == Decimal("50")
    assert l.procesos.count() == 1
    proc = l.procesos.first()
    assert proc.tipo == "impresion" and proc.por_pieza is True and proc.costo == Decimal("15")


def test_duplicar_no_copia_cotizaciones_ni_facturas(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion
    from apps.facturacion.models import Factura
    from apps.los_proyectos.models import Proyecto
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="Original", cliente=cli, creado_por=autor)
    Cotizacion.objects.create(cliente=cli, proyecto=proy, titulo="Cot", creado_por=autor)
    Factura.objects.create(cliente=cli, proyecto=proy, titulo="Fac", creado_por=autor)

    nuevo = duplicar_proyecto(proy, nombre="Clon", actor=autor)
    assert nuevo.cotizaciones.count() == 0
    assert nuevo.facturas.count() == 0
