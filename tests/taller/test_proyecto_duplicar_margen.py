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
    linea = lineas[0]
    assert linea.servicio_id == serv.pk
    assert linea.proveedor_id == prov.pk
    assert linea.precio_unitario == Decimal("120")
    assert linea.costo_unitario == Decimal("50")
    assert linea.procesos.count() == 1
    proc = linea.procesos.first()
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


# ── Lo que la copia perdía (LC 2026-08-18, Oscar) ───────────────────────────


def _proyecto_completo(cliente_factory, usuario_factory):
    """Un proyecto con TODO lo que se ve en una tarjeta: alias, descripción,
    orden, cobros extra, procesos y una opción de volumen."""
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import (
        Proyecto,
        ProyectoProductoEscala,
        ProyectoProductoProceso,
    )
    from apps.los_proyectos.models.venta import ProyectoProductoVenta

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="Original", cliente=cli, creado_por=autor)
    prov = Proveedor.objects.create(razon_social="Crea Blanks")
    serv = _servicio(nombre="TShirt Oversize Color")

    primera = _linea(proy, serv, cantidad=10, precio="120", costo="50", prov=prov)
    primera.nombre_proyecto = "TShirt Modelo Janet"
    primera.nota = "Color: Beige\nBordado frontal"
    primera.orden = 3
    # Foto PROPIA del uso: la tiene porque la línea tiene alias (ver
    # `ProyectoProducto.imagen_destino`).
    primera.imagen_file_id = "drive-janet-1"
    primera.imagen_url = "https://drive/janet"
    primera.save()
    ProyectoProductoProceso.objects.create(
        producto=primera, tipo="impresion", proveedor=prov,
        costo=Decimal("15"), costo_expr="10+5", por_pieza=True, orden=0)
    ProyectoProductoVenta.objects.create(
        producto=primera, orden=0, descripcion="Ponchado", cantidad=2,
        precio_unitario=Decimal("350"), precio_expr="175*2")
    ProyectoProductoEscala.objects.create(
        producto=primera, orden=0, cantidad=50, precio_unitario=Decimal("110"),
        activa=True)
    return autor, proy, primera


def test_la_copia_conserva_el_nombre_que_ve_el_cliente(cliente_factory, usuario_factory):
    """El alias del producto en el proyecto se perdía: la copia volvía al nombre
    del catálogo, y con él cambiaba lo que dice la cotización."""
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, _ = _proyecto_completo(cliente_factory, usuario_factory)
    linea = duplicar_proyecto(proy, nombre="Clon", actor=autor).productos.get()
    assert linea.nombre_proyecto == "TShirt Modelo Janet"
    assert linea.nombre_visible == "TShirt Modelo Janet"
    assert linea.nota.startswith("Color: Beige")
    assert linea.orden == 3


def test_la_copia_conserva_lo_que_se_le_cobra_aparte(cliente_factory, usuario_factory):
    """Los procesos de VENTA no se copiaban, así que la copia salía más barata
    que el original sin que nada lo avisara."""
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, original = _proyecto_completo(cliente_factory, usuario_factory)
    linea = duplicar_proyecto(proy, nombre="Clon", actor=autor).productos.get()
    venta = linea.ventas.get()
    assert venta.descripcion == "Ponchado"
    assert venta.cantidad == 2
    assert venta.precio_unitario == Decimal("350.00")
    assert venta.precio_expr == "175*2"          # la cuenta escrita también
    # Y por lo tanto la copia cobra lo mismo que el original.
    assert linea.subtotal_con_ventas == original.subtotal_con_ventas


def test_la_copia_conserva_las_cuentas_escritas(cliente_factory, usuario_factory):
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, _ = _proyecto_completo(cliente_factory, usuario_factory)
    linea = duplicar_proyecto(proy, nombre="Clon", actor=autor).productos.get()
    assert linea.procesos.get().costo_expr == "10+5"


def test_la_copia_conserva_las_opciones_de_volumen(cliente_factory, usuario_factory):
    """Ya se copiaban; el test las fija junto a las otras dos, que es donde se
    nota si alguien vuelve a olvidar una relación de la línea."""
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, _ = _proyecto_completo(cliente_factory, usuario_factory)
    linea = duplicar_proyecto(proy, nombre="Clon", actor=autor).productos.get()
    escala = linea.escalas.get()
    assert escala.cantidad == 50
    assert escala.activa is True
    assert linea.cantidad_efectiva == 50


def test_la_copia_sigue_sin_heredar_el_dinero(cliente_factory, usuario_factory):
    """La exclusión dura de siempre: los cobros extra son PRECIO, no un flujo de
    dinero histórico. El egreso ya registrado no viaja."""
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, _ = _proyecto_completo(cliente_factory, usuario_factory)
    nuevo = duplicar_proyecto(proy, nombre="Clon", actor=autor)
    assert nuevo.productos.get().egreso_id is None
    assert nuevo.monto_cobrado == Decimal("0")
    assert nuevo.estado == "por_cotizar"


def test_la_copia_conserva_la_foto(cliente_factory, usuario_factory):
    """Oscar: «las fotos van ligadas a su alias o nombre y sí viajan al
    duplicar». Se copia la referencia al archivo de Drive, no el archivo."""
    from apps.los_proyectos.services_duplicar import duplicar_proyecto

    autor, proy, original = _proyecto_completo(cliente_factory, usuario_factory)
    linea = duplicar_proyecto(proy, nombre="Clon", actor=autor).productos.get()
    assert linea.imagen_file_id == "drive-janet-1"
    assert linea.imagen_es_propia is True
    assert linea.imagen_efectiva_file_id == original.imagen_efectiva_file_id


@pytest.mark.django_db
def test_duplicar_una_linea_suelta_tambien_se_lleva_la_foto(
        client, cliente_factory, usuario_factory):
    """El ⧉ de la tarjeta. REVIERTE la decisión de Ago12-B: si el alias viaja y
    la foto va ligada al alias, la foto viaja con él."""
    from django.urls import reverse

    autor, proy, original = _proyecto_completo(cliente_factory, usuario_factory)
    client.force_login(autor)
    resp = client.post(
        reverse("proyectos-duplicar-producto", args=[proy.pk, original.pk]))
    assert resp.status_code in (200, 204, 302)

    copia = proy.productos.exclude(pk=original.pk).get()
    assert copia.nombre_proyecto == "TShirt Modelo Janet"
    assert copia.imagen_file_id == "drive-janet-1"
    # Y lo que NO se hereda sigue sin heredarse: el egreso es marca de
    # idempotencia de producción.
    assert copia.egreso_id is None

