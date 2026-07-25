"""Botón «Resumir actividad» del recuadro de El Chalán en el Dashboard (2026-07).

- El reporte es DETERMINISTA (queries, no IA) y respeta permisos por sección.
- El modal sale en texto simple: títulos en negritas, renglones con <br>.
- Sweep nombre > código: el detalle de cotización titula con el proyecto.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _seccion(secciones, titulo):
    for s in secciones:
        if s["titulo"] == titulo:
            return s
    return None


def _tarea(proyecto, titulo, **kw):
    from apps.el_pizarron.models import Tarea
    return Tarea.objects.create(proyecto=proyecto, titulo=titulo, **kw)


# ── URGENTES ─────────────────────────────────────────────────────────────


def test_urgentes_junta_prioridad_alta_y_vencidas_ordenadas(proyecto_factory, usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Correas")
    hoy = dt.date.today()
    _tarea(p, "Alta lejana", prioridad="alta", fecha_compromiso=hoy + dt.timedelta(days=10))
    _tarea(p, "Vencida", prioridad="media", fecha_compromiso=hoy - dt.timedelta(days=2))
    _tarea(p, "Normal futura", prioridad="media", fecha_compromiso=hoy + dt.timedelta(days=3))

    urg = _seccion(secciones_pendientes(admin), "URGENTES")
    assert urg is not None
    texto = "\n".join(urg["lineas"])
    assert "Vencida" in texto and "Alta lejana" in texto
    assert "Normal futura" not in texto           # ni alta ni vencida
    assert urg["lineas"][0].startswith("Vencida")  # fecha más cercana arriba
    assert p.cliente.razon_social in urg["lineas"][0]


def test_tareas_archivadas_o_cerradas_no_entran(proyecto_factory, usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    hoy = dt.date.today()
    _tarea(p, "Archivada urgente", prioridad="alta", archivada=True,
           fecha_compromiso=hoy - dt.timedelta(days=1))
    _tarea(p, "Cerrada urgente", prioridad="alta", estado="completada",
           fecha_compromiso=hoy - dt.timedelta(days=1))

    urg = _seccion(secciones_pendientes(admin), "URGENTES")
    assert urg["lineas"] == []


# ── Secciones por persona ────────────────────────────────────────────────


def test_seccion_por_persona_usa_nombre_de_pila_en_mayusculas(proyecto_factory, usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    alex = usuario_factory(rol="disenador", email="alex@ejemplo.com")
    alex.nombre_completo = "Alex Ramírez"
    alex.save()
    p = proyecto_factory()
    _tarea(p, "Diseñar cajas", asignada_a=alex, fecha_compromiso=dt.date.today())

    secs = secciones_pendientes(admin)
    alexs = _seccion(secs, "ALEX")
    assert alexs is not None
    assert any("Diseñar cajas" in linea for linea in alexs["lineas"])
    # Va después de URGENTES y antes de MISIONES (orden fijo del reporte).
    titulos = [s["titulo"] for s in secs]
    assert titulos.index("URGENTES") < titulos.index("ALEX") < titulos.index("MISIONES")


# ── MISIONES ─────────────────────────────────────────────────────────────


def test_misiones_lista_mandados_abiertos(proyecto_factory, usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Entrega Michoacana")
    _tarea(p, "Llevar playeras", tipo="entrega", fecha_compromiso=dt.date.today())

    mis = _seccion(secciones_pendientes(admin), "MISIONES")
    assert any("Llevar playeras" in linea for linea in mis["lineas"])
    assert "sin runner" in mis["lineas"][0]


# ── TIZAYUCA · FACTURAS X EMITIR · COTIZACIONES · FACTURAS X COBRAR ──────


def test_tizayuca_lista_proyectos_con_el_proveedor(proyecto_factory, usuario_factory):
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social=PROVEEDOR_CALCULADORA, activo=True)
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat")
    srv = Servicio.objects.create(nombre="Funda", categoria=cat, activo=True,
                                  precio_base="100.00")
    con = proyecto_factory(nombre="Fundas Tizayuca")
    ProyectoProducto.objects.create(proyecto=con, servicio=srv, cantidad=1, proveedor=prov)
    proyecto_factory(nombre="Otro sin proveedor")

    tiz = _seccion(secciones_pendientes(admin), "TIZAYUCA")
    texto = "\n".join(tiz["lineas"])
    assert "Fundas Tizayuca" in texto
    assert "Otro sin proveedor" not in texto


def test_facturas_por_emitir_excluye_proyectos_ya_facturados(proyecto_factory, usuario_factory):
    from apps.facturacion.models import Factura
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    sin_fac = proyecto_factory(nombre="Sin factura", estado="en_proceso_produccion")
    con_fac = proyecto_factory(nombre="Ya facturado", estado="entregado")
    proyecto_factory(nombre="Apenas cotizando", estado="por_cotizar")
    Factura.objects.create(
        cliente=con_fac.cliente, proyecto=con_fac, estado="emitida", concepto="Servicios",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
    )

    secs = secciones_pendientes(admin)
    emitir = "\n".join(_seccion(secs, "FACTURAS X EMITIR")["lineas"])
    assert sin_fac.nombre in emitir
    assert "Ya facturado" not in emitir
    assert "Apenas cotizando" not in emitir     # aún no es venta confirmada
    # …pero sí sale en COTIZACIONES.
    assert "Apenas cotizando" in "\n".join(_seccion(secs, "COTIZACIONES")["lineas"])


def test_facturas_por_cobrar_solo_con_saldo(proyecto_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem
    from apps.taller_home.pendientes import secciones_pendientes

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = Factura.objects.create(
        cliente=p.cliente, proyecto=p, estado="emitida", concepto="Servicios",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
    )
    FacturaItem.objects.create(factura=fac, descripcion="Trabajo", cantidad=1,
                               precio_unitario=1000)
    pagada = Factura.objects.create(
        cliente=p.cliente, proyecto=p, estado="cobrada_total", concepto="Otra",
        fecha_emision=dt.date.today(), fecha_vencimiento=dt.date.today(),
    )

    cobrar = "\n".join(_seccion(secciones_pendientes(admin), "FACTURAS X COBRAR")["lineas"])
    assert fac.folio_display in cobrar
    assert pagada.folio_display not in cobrar


def test_disenador_no_ve_secciones_de_facturacion(proyecto_factory, usuario_factory):
    from apps.taller_home.pendientes import secciones_pendientes

    disenador = usuario_factory(rol="disenador")
    titulos = [s["titulo"] for s in secciones_pendientes(disenador)]
    assert "FACTURAS X EMITIR" not in titulos
    assert "FACTURAS X COBRAR" not in titulos
    assert "URGENTES" in titulos


# ── Vistas / modal ───────────────────────────────────────────────────────


def test_modal_resumen_es_texto_simple_con_negritas(client, proyecto_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    _tarea(p, "Pendiente urgente", prioridad="alta", fecha_compromiso=dt.date.today())
    client.force_login(admin)

    r = client.get("/resumen/actividad/", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "<b>URGENTES</b>" in html
    assert "<br>" in html
    assert "Pendiente urgente" in html
    assert "Copiar" in html


def test_modal_resumen_pide_sesion(client):
    r = client.get("/resumen/actividad/", HTTP_HX_REQUEST="true")
    assert r.status_code in (302, 403)


def test_dashboard_muestra_el_boton_de_resumen(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()
    assert "Resumir actividad" in html
    assert "Reporta updates, consulta finanzas" in html
    assert ">Enviar<" in html


# ── Nombre del proyecto > código ─────────────────────────────────────────


def test_detalle_cotizacion_titula_con_el_nombre_del_proyecto(client, proyecto_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Correas para las perras")
    cot = Cotizacion.objects.create(
        codigo="COT-2026-7777", cliente=p.cliente, proyecto=p, titulo="Propuesta",
        estado="generada", creado_por=admin, fecha_emision=dt.date.today(),
    )
    client.force_login(admin)

    html = client.get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert "Correas para las perras" in html
    assert "COT-2026-7777" in html  # el código sigue visible, pero de subtítulo
