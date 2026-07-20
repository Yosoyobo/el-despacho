"""Sprint 2 — Optimización de UX, Modales y Flujos de Captura.

Cubre los 9 items del sprint (numeración del handoff entre paréntesis):
- item 1  Formateo global de cifras: `|dinero` trunca los .00.
- item 2  Descripción de ingreso opcional + etiqueta «Notas».
- item 5  Modal de ingreso sin selector de cliente (se hereda del proyecto)
          ni pastillas legacy.
- item 4  Modal de proyecto sin pastillas de clientes + semáforo de estado.
- item 3  Mini-calendario sin botón «Quitar fecha» + título centrado.
- item 6  Orden por categoría (toggle asc/desc) en la lista de productos.
- item 11 Columna Proveedor al 3er lugar.
- item 7  Fila del catálogo navega al panel de edición (sin botón «Editar»);
          el panel incluye el historial de usos.
- item 13 Producto nuevo se agrega al final (append).
"""

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _categoria(nombre="General"):
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre=nombre)


# ── item 1 — |dinero trunca los centavos .00 ─────────────────────────────────

def test_dinero_trunca_enteros_y_conserva_centavos():
    from cuentas.templatetags.forms_helpers import dinero, dinero_sin_signo
    assert dinero(95) == "$95"
    assert dinero(Decimal("95.00")) == "$95"
    assert dinero(1234) == "$1,234"
    assert dinero(Decimal("1234.00")) == "$1,234"
    assert dinero(Decimal("95.50")) == "$95.50"
    assert dinero(Decimal("1234.56")) == "$1,234.56"
    assert dinero(Decimal("-500.00")) == "-$500"
    assert dinero(Decimal("-500.25")) == "-$500.25"
    assert dinero(None) == "—"
    assert dinero_sin_signo(Decimal("1234.00")) == "1,234"
    assert dinero_sin_signo(Decimal("1234.50")) == "1,234.50"


# ── item 2 — descripción de ingreso opcional + «Notas» ───────────────────────

def test_ingreso_descripcion_opcional_label_notas():
    from apps.tesoreria.forms import IngresoForm
    f = IngresoForm()
    assert f.fields["descripcion"].required is False
    assert f.fields["descripcion"].label == "Notas"


def test_ingreso_guarda_sin_descripcion(client, usuario_factory):
    from datetime import date

    from apps.tesoreria.models import Ingreso
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(reverse("tesoreria:ingreso-nuevo"), {
        "subtotal": "300.00", "fecha": date.today().isoformat(),
        "metodo": "tarjeta",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    ing = Ingreso.objects.get(subtotal=Decimal("300.00"))
    assert ing.descripcion == ""


# ── item 5 — modal de ingreso sin cliente + hereda del proyecto ──────────────

def test_modal_ingreso_sin_selector_cliente_ni_pastillas(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("tesoreria:ingreso-nuevo"), HTTP_HX_REQUEST="true").content.decode()
    assert 'id="id_cliente"' not in html          # selector de cliente retirado
    assert "data-pick-select" not in html          # pastillas legacy retiradas
    assert "Nuevo cliente" not in html             # alta inline de cliente retirada
    assert 'name="proyecto"' in html               # el proyecto se conserva
    assert "se toma automáticamente del proyecto" in html


def test_ingreso_hereda_cliente_del_proyecto(client, usuario_factory, proyecto_factory):
    from datetime import date

    from apps.tesoreria.models import Ingreso
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    resp = client.post(reverse("tesoreria:ingreso-nuevo"), {
        "subtotal": "500.00", "fecha": date.today().isoformat(),
        "metodo": "tarjeta", "proyecto": proy.pk,
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    ing = Ingreso.objects.get(subtotal=Decimal("500.00"))
    assert ing.cliente_id == proy.cliente_id


# ── item 4 — modal de proyecto sin pastillas de cliente + semáforo ───────────

def test_modal_proyecto_sin_pastillas_cliente_con_semaforo(client, usuario_factory, cliente_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cliente_factory(creado_por=autor)
    html = client.get(reverse("proyectos-nuevo"), HTTP_HX_REQUEST="true").content.decode()
    assert "data-set-select" not in html   # pastillas de cliente retiradas
    assert 'name="cliente"' in html or 'id_cliente' in html  # combobox conservado
    assert "estado-chip" in html           # semáforo de estado (bloques de color)
    assert "--ec:" in html


# ── item 3 — mini-calendario sin «Quitar fecha» + título centrado ────────────

def test_minical_sin_quitar_fecha_titulo_centrado(client, usuario_factory, cliente_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cliente_factory(creado_por=autor)
    # El modal de proyecto pasa con_quitar=True a dos minicals; ya no debe pintar botón.
    html = client.get(reverse("proyectos-nuevo"), HTTP_HX_REQUEST="true").content.decode()
    assert "Quitar fecha" not in html
    assert "data-mc-titulo" in html
    assert "flex-1 text-center" in html    # título del mes centrado


# ── item 6 — orden por categoría (toggle asc/desc) ───────────────────────────

def test_catalogo_orden_por_categoria(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat_a = _categoria("Alfa")
    cat_z = _categoria("Zeta")
    Servicio.objects.create(nombre="Producto en Zeta", precio_base="10", categoria=cat_z)
    Servicio.objects.create(nombre="Producto en Alfa", precio_base="10", categoria=cat_a)
    client.force_login(usuario_factory(rol="super_admin"))
    # asc: Alfa antes que Zeta
    html = client.get("/catalogo/?orden=categoria").content.decode()
    assert html.index("Producto en Alfa") < html.index("Producto en Zeta")
    # desc: Zeta antes que Alfa
    html_desc = client.get("/catalogo/?orden=-categoria").content.decode()
    assert html_desc.index("Producto en Zeta") < html_desc.index("Producto en Alfa")
    # la cabecera Categoría es un link de orden (en estado neutro apunta a asc)
    html_neutro = client.get("/catalogo/").content.decode()
    assert "orden=categoria" in html_neutro


# ── item 11 — columna Proveedor al 3er lugar ─────────────────────────────────

def test_catalogo_proveedor_tercera_columna(client, usuario_factory):
    resp = None
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/catalogo/")
    cabeceras = [c["label"] for c in resp.context["cabeceras_catalogo"]]
    assert cabeceras[:3] == ["Nombre", "Categoría", "Proveedores"]
    assert cabeceras.index("Proveedores") < cabeceras.index("Usos")


# ── item 7 — fila navega al panel de edición; sin botón «Editar» ─────────────

def test_catalogo_fila_navega_al_panel_de_edicion(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Playera", precio_base="100", categoria=_categoria())
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get("/catalogo/").content.decode()
    editar_url = reverse("catalogo-editar", args=[srv.pk])
    assert f'data-href="{editar_url}"' in html   # la fila entera va al panel


def test_panel_edicion_incluye_historial_de_usos(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Lona", precio_base="100", categoria=_categoria())
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("catalogo-editar", args=[srv.pk])).content.decode()
    assert "Historial de usos" in html
    assert 'id="usos-historial"' in html


# ── item 13 — producto nuevo se agrega al final (append) ──────────────────────

def test_siguiente_orden_producto_es_max_mas_uno(proyecto_factory, usuario_factory):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.views import _siguiente_orden_producto
    proy = proyecto_factory()
    cat = _categoria()
    s1 = Servicio.objects.create(nombre="A", precio_base="10", categoria=cat)
    s2 = Servicio.objects.create(nombre="B", precio_base="10", categoria=cat)
    ProyectoProducto.objects.create(proyecto=proy, servicio=s1, cantidad=1, orden=0)
    ProyectoProducto.objects.create(proyecto=proy, servicio=s2, cantidad=1, orden=5)
    assert _siguiente_orden_producto(proy) == 6


def test_agregar_producto_modal_lo_pone_al_final(client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import ProyectoProducto
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    cat = _categoria()
    s1 = Servicio.objects.create(nombre="Primero", precio_base="10", categoria=cat)
    s2 = Servicio.objects.create(nombre="Segundo", precio_base="10", categoria=cat)
    ProyectoProducto.objects.create(proyecto=proy, servicio=s1, cantidad=1, orden=0)
    url = reverse("proyectos-agregar-producto", args=[proy.pk])
    resp = client.post(url, {"servicio": s2.pk, "cantidad": "1"}, HTTP_HX_REQUEST="true")
    assert resp.status_code in (204, 302)
    nuevo = ProyectoProducto.objects.get(proyecto=proy, servicio=s2)
    assert nuevo.orden > 0  # append: quedó después del primero (orden 0)
