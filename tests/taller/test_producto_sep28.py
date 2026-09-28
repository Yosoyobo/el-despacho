"""LC 2026-09-28 — Deploy 2 (producto) del sprint de pendientes.

Decisiones de Oscar, literales (`docs/SPRINT-Pendientes-Sep28.md`):

1. **Proveedor ★ al cambiarlo → «preguntar al guardar»**, y el modal ofrece
   «sólo los que se pueden (vivos, sin egreso de esa línea, sin cotización
   pagada, con el proveedor anterior), todos marcados».
2. **Color de tarjeta → sólo alias y catálogo** (la descripción deja de decidir).
3. **HEIC → convertir a JPEG** (`pillow-heif`).
4. **@persona crea una tarea ligada al producto**, en el campo de tareas del
   producto, directo y sin IA; fecha: la que se escriba o la entrega del
   proyecto.
5. **Plegado móvil** de la ficha del cliente y de la ficha del producto.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller]


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


@pytest.fixture
def cliente(db, cliente_factory):
    return cliente_factory(razon_social="Optimist")


def _prov(razon):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=razon, activo=True)


def _proyecto(cliente, nombre="Vivo", **extra):
    from apps.los_proyectos.models import Proyecto
    extra.setdefault("estado", "en_proceso_diseno")
    return Proyecto.objects.create(nombre=nombre, cliente=cliente, **extra)


def _linea(proyecto, servicio, **extra):
    from apps.los_proyectos.models import ProyectoProducto
    extra.setdefault("cantidad", 10)
    return ProyectoProducto.objects.create(proyecto=proyecto, servicio=servicio, **extra)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Proveedor ★: «¿También en estos proyectos?»
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def producto_con_dos(categoria):
    """Un producto cuyo principal es Alfa, que también puede surtir Zeta."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria,
                                  costo=50, precio_base=100, proveedor_principal=alfa)
    srv.proveedores.set([alfa, zeta])
    return srv, alfa, zeta


def _post_principal(client, srv, categoria, ids):
    return client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": srv.nombre, "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(i) for i in ids],
        "proveedores_orden": ",".join(str(i) for i in ids),
    })


def test_elegibles_solo_las_vivas_con_el_proveedor_anterior(
        cliente, producto_con_dos):
    """La regla que acordó Oscar, línea por línea."""
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.propagacion import lineas_para_proveedor
    from apps.tesoreria.models import CentroDeCosto, Egreso

    srv, alfa, zeta = producto_con_dos
    buena = _linea(_proyecto(cliente, "Bueno"), srv, proveedor=alfa)
    # Un proveedor puesto a mano para ese proyecto es una decisión: no se ofrece.
    _linea(_proyecto(cliente, "A mano"), srv, proveedor=zeta)
    # Cerrado y archivado: ya no se tocan.
    _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    _linea(_proyecto(cliente, "Archivado", archivado=True), srv, proveedor=alfa)
    # Con egreso: ese dinero ya salió.
    centro, _ = CentroDeCosto.objects.get_or_create(
        slug="insumos-de-proyecto", defaults={"nombre": "Insumos de proyecto"})
    egreso = Egreso.objects.create(monto=Decimal("500.00"), descripcion="x",
                                   centro_de_costo=centro, fecha=dt.date.today())
    _linea(_proyecto(cliente, "Pagado a proveedor"), srv, proveedor=alfa, egreso=egreso)
    # Con cotización pagada: lo facturado no se mueve.
    pagado = _proyecto(cliente, "Cotización pagada")
    Cotizacion.objects.create(cliente=cliente, proyecto=pagado, version=1, estado="pagada")
    _linea(pagado, srv, proveedor=alfa)

    assert [linea.pk for linea in lineas_para_proveedor(srv, alfa.pk)] == [buena.pk]


def test_cambiar_el_principal_abre_el_modal_una_sola_vez(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    """«Preguntar al guardar»: el modal se pide tras el redirect, y recargar la
    ficha ya no vuelve a preguntar (la pregunta sale de la sesión)."""
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    resp = _post_principal(client, srv, categoria, [zeta.pk, alfa.pk])
    assert resp.status_code == 302
    srv.refresh_from_db()
    assert srv.proveedor_principal_id == zeta.pk

    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert f"/catalogo/{srv.pk}/propagar-proveedor?anterior={alfa.pk}" in html
    assert 'hx-trigger="load"' in html

    otra_vez = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in otra_vez


def test_sin_elegibles_no_aparece_nada(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))
    _post_principal(client, srv, categoria, [zeta.pk, alfa.pk])
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in html


def test_guardar_sin_cambiar_el_principal_no_pregunta(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))
    _post_principal(client, srv, categoria, [alfa.pk, zeta.pk])
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in html


def test_el_modal_lista_los_elegibles_todos_marcados(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    l1 = _linea(_proyecto(cliente, "Gorras Kari"), srv, proveedor=alfa)
    l2 = _linea(_proyecto(cliente, "Playeras Kari"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    html = client.get(f"/catalogo/{srv.pk}/propagar-proveedor", {"anterior": alfa.pk},
                      HTTP_HX_REQUEST="true").content.decode()
    assert "¿También en estos proyectos?" in html
    for linea in (l1, l2):
        assert f'name="lineas" value="{linea.pk}" checked' in html
    assert "Gorras Kari" in html and "Playeras Kari" in html


def test_al_confirmar_solo_cambian_las_marcadas(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    marcada = _linea(_proyecto(cliente, "Sí"), srv, proveedor=alfa)
    desmarcada = _linea(_proyecto(cliente, "No"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    resp = client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                       {"anterior": alfa.pk, "lineas": [str(marcada.pk)]},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == f"/catalogo/{srv.pk}/editar"
    marcada.refresh_from_db()
    desmarcada.refresh_from_db()
    assert marcada.proveedor_id == zeta.pk
    assert desmarcada.proveedor_id == alfa.pk


def test_el_post_vuelve_a_validar_cada_linea(
        client, usuario_factory, cliente, producto_con_dos):
    """Un id que llega del navegador no se cree: una línea cerrada, una con otro
    proveedor o una de otro producto se saltan aunque vengan marcadas."""
    from apps.el_catalogo.models import Servicio

    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    cerrada = _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    ajena_srv = Servicio.objects.create(nombre="Gorra", categoria=srv.categoria,
                                        costo=10, precio_base=20)
    ajena = _linea(_proyecto(cliente, "Ajeno"), ajena_srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                {"anterior": alfa.pk, "lineas": [str(cerrada.pk), str(ajena.pk)]},
                HTTP_HX_REQUEST="true")
    for linea in (cerrada, ajena):
        linea.refresh_from_db()
        assert linea.proveedor_id == alfa.pk


def test_sin_permiso_de_proyectos_no_se_aplica(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    linea = _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                       {"anterior": alfa.pk, "lineas": [str(linea.pk)]})
    assert resp.status_code in (302, 403)
    linea.refresh_from_db()
    assert linea.proveedor_id == alfa.pk


def test_el_evento_esta_tipado():
    from typing import get_args

    from lib.portavoz_eventos import EventoTipo
    assert "catalogo.proveedor_propagado" in get_args(EventoTipo)
