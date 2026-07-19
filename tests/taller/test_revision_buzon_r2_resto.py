"""Revisión del buzón — Ronda 2, resto (2026-07): las demás acciones rápidas del
Dashboard como form-in-modal + Nuevo proyecto quick-create con mini-Chalán."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _categoria(nombre="General"):
    from apps.el_catalogo.models import CategoriaServicio
    cat = CategoriaServicio.objects.filter(activa=True).first()
    return cat or CategoriaServicio.objects.create(nombre=nombre, color="#667085", orden=1)


def _servicio(nombre="Playera", precio="100.00", costo="40.00"):
    from apps.el_catalogo.models import Servicio
    return Servicio.objects.create(
        nombre=nombre, precio_base=Decimal(precio), costo=Decimal(costo), categoria=_categoria(),
    )


def _proveedor(nombre="Proveedor X"):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=nombre, activo=True)


def _centro():
    from apps.tesoreria.models import CentroDeCosto
    c = CentroDeCosto.objects.filter(activo=True).first()
    return c or CentroDeCosto.objects.create(nombre="General", slug="general", tipo="general")


# ── Nuevo proveedor ─────────────────────────────────────────────────────────

def test_proveedor_modal_get_htmx(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("catalogo-proveedor-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-proveedor" in cuerpo
    assert "Nuevo proveedor" in cuerpo
    assert "hx-post" in cuerpo


def test_proveedor_modal_post_htmx_crea(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(reverse("catalogo-proveedor-nuevo"), {"razon_social": "Maracas Don José"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Proveedor.objects.filter(razon_social="Maracas Don José").exists()


def test_proveedor_fallback_full(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("catalogo-proveedor-nuevo"))
    assert resp.status_code == 200
    assert b"modal-slot" in resp.content  # extiende base.html


# ── Nuevo producto ──────────────────────────────────────────────────────────

def test_producto_modal_get_htmx(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("catalogo-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-producto" in cuerpo
    assert "Nuevo producto" in cuerpo
    # La imagen no se sube en alta: se avisa que va al editar.
    assert "al editarlo" in cuerpo


def test_producto_modal_post_htmx_crea(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    cat = _categoria()
    resp = client.post(reverse("catalogo-nuevo"), {
        "nombre": "Gorra bordada", "unidad": "pieza", "costo": "30",
        "precio_base": "80", "categoria": cat.pk, "activo": "on",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Servicio.objects.filter(nombre="Gorra bordada").exists()


def test_producto_fallback_full(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("catalogo-nuevo"))
    assert resp.status_code == 200
    assert b"modal-slot" in resp.content


# ── Nuevo cliente ───────────────────────────────────────────────────────────

def _datos_cliente(razon="ACME S.A."):
    from apps.la_cartera.forms import ClienteContactoFormSet
    pfx = ClienteContactoFormSet().prefix
    return {
        "razon_social": razon, "estado": "activo",
        f"{pfx}-TOTAL_FORMS": "0", f"{pfx}-INITIAL_FORMS": "0",
        f"{pfx}-MIN_NUM_FORMS": "0", f"{pfx}-MAX_NUM_FORMS": "1000",
    }


def test_cliente_modal_get_htmx(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("cartera-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-cliente" in cuerpo
    assert "Nuevo cliente" in cuerpo
    # LC Fase 2: ultra-compacto — Nombre + estado (pastillas); sin formset de Contactos.
    assert "Nombre" in cuerpo
    assert "Prospecto" in cuerpo
    assert "Contactos" not in cuerpo


def test_cliente_modal_post_htmx_crea(client, usuario_factory):
    from apps.la_cartera.models import Cliente
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(reverse("cartera-nuevo"), _datos_cliente("ACME S.A."), HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Cliente.objects.filter(razon_social__iexact="ACME S.A.").exists()


def test_cliente_fallback_full(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("cartera-nuevo"))
    assert resp.status_code == 200
    assert b"modal-slot" in resp.content


# ── Nuevo ingreso ───────────────────────────────────────────────────────────

def test_ingreso_modal_get_htmx(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("tesoreria:ingreso-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-ingreso" in cuerpo
    assert "data-iva-block" in cuerpo  # calculadora de IVA
    assert "data-minical" in cuerpo    # mini-calendario


def test_ingreso_modal_post_htmx_crea(client, usuario_factory):
    from datetime import date

    from apps.tesoreria.models import Ingreso
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(reverse("tesoreria:ingreso-nuevo"), {
        "subtotal": "150.00", "fecha": date.today().isoformat(),
        "metodo": "tarjeta", "moneda": "MXN", "descripcion": "Anticipo cliente",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Ingreso.objects.filter(subtotal=Decimal("150.00")).exists()


# ── Nuevo egreso ────────────────────────────────────────────────────────────

def test_egreso_modal_get_htmx(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(reverse("tesoreria:egreso-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-egreso" in cuerpo
    assert 'name="comprobante"' in cuerpo          # input de archivo simple
    assert 'hx-encoding="multipart/form-data"' in cuerpo


def test_egreso_modal_post_htmx_crea(client, usuario_factory):
    from datetime import date

    from apps.tesoreria.models import Egreso
    client.force_login(usuario_factory(rol="super_admin"))
    prov, centro = _proveedor(), _centro()
    resp = client.post(reverse("tesoreria:egreso-nuevo"), {
        "subtotal": "200.00", "fecha": date.today().isoformat(),
        "proveedor": prov.pk, "centro_de_costo": centro.pk,
        "estado_pago": "pagado", "metodo": "tarjeta_empresa", "moneda": "MXN",
        "descripcion": "Compra de insumos",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Egreso.objects.filter(subtotal=Decimal("200.00")).exists()


# ── Nuevo proyecto: quick-create + mini-Chalán ──────────────────────────────

def test_proyecto_modal_get_htmx(client, usuario_factory, cliente_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cliente_factory(creado_por=autor)
    resp = client.get(reverse("proyectos-nuevo"), HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "data-modal-proyecto" in cuerpo
    assert 'name="productos_texto"' in cuerpo  # mini-Chalán (super_admin tiene chalan)
    assert "Mañana" in cuerpo                   # Entrega usa Mañana (R1)


def test_proyecto_modal_post_sin_productos_crea_y_redirige(client, usuario_factory, cliente_factory):
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    from apps.los_proyectos.models.estado import EstadoProyecto
    estado = EstadoProyecto.objects.filter(activo=True).order_by("orden").first()
    resp = client.post(reverse("proyectos-nuevo"), {
        "nombre": "Playeras Congreso", "cliente": cli.pk, "estado": estado.slug,
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Proyecto.objects.filter(nombre="Playeras Congreso").exists()


def test_proyecto_modal_post_con_productos_muestra_preview(client, usuario_factory, cliente_factory, monkeypatch):
    from apps.los_proyectos import productos_ia
    from apps.los_proyectos.models import Proyecto
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    from apps.los_proyectos.models.estado import EstadoProyecto
    estado = EstadoProyecto.objects.filter(activo=True).order_by("orden").first()

    def _fake(*, proyecto, texto, usuario):
        return {"ok": True, "error": "", "productos": [
            {"nombre": "Playera", "cantidad": 100, "precio_unitario": "80.00", "nota": "", "servicio_id": None, "es_nuevo": True},
        ]}
    monkeypatch.setattr(productos_ia, "interpretar_productos", _fake)

    resp = client.post(reverse("proyectos-nuevo"), {
        "nombre": "Evento X", "cliente": cli.pk, "estado": estado.slug,
        "productos_texto": "100 playeras",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200  # preview, no redirect todavía
    cuerpo = resp.content.decode()
    assert "data-modal-productos-ia" in cuerpo
    assert "Playera" in cuerpo
    assert 'name="productos_json"' in cuerpo
    # El proyecto YA se creó (el preview es solo para los productos).
    assert Proyecto.objects.filter(nombre="Evento X").exists()


def test_proyecto_productos_ia_aplicar_agrega_seleccionados(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    srv = _servicio("Taza")
    productos = [{"nombre": srv.nombre, "cantidad": 3, "precio_unitario": "", "nota": "", "servicio_id": srv.pk, "es_nuevo": False}]
    resp = client.post(
        reverse("proyectos-productos-ia-aplicar", args=[proy.pk]),
        {"productos_json": json.dumps(productos), "sel": "0"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    pp = ProyectoProducto.objects.filter(proyecto=proy, servicio=srv).first()
    assert pp is not None and pp.cantidad == 3


def test_productos_ia_aplicar_ignora_no_seleccionados(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    srv = _servicio("Lona")
    productos = [{"nombre": srv.nombre, "cantidad": 2, "servicio_id": srv.pk, "es_nuevo": False, "precio_unitario": "", "nota": ""}]
    # sin `sel` → nada seleccionado.
    resp = client.post(
        reverse("proyectos-productos-ia-aplicar", args=[proy.pk]),
        {"productos_json": json.dumps(productos)},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert not ProyectoProducto.objects.filter(proyecto=proy).exists()
