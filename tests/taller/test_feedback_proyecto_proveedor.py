"""Ronda de feedback Oscar (página de proyecto):

- agregar_producto_proyecto: el Chalán agrega productos a un proyecto SIN
  importar su estado, y se ven siempre.
- toggle de IVA por proveedor (solo este proyecto).
- CAPS en nombre de cliente vía ejecutor del Chalán.
- filtro `dinero_corto`.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat FB")
    serv = Servicio.objects.create(
        nombre="Playeras", categoria=cat,
        precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True)
    prov = Proveedor.objects.create(razon_social="Textiles SA", activo=True)
    return {"cat": cat, "serv": serv, "prov": prov}


# ── agregar_producto_proyecto (item 16) ───────────────────────────────────────

def test_agregar_producto_sin_importar_estado(proyecto_factory, catalogo, usuario_factory, _on_commit_inmediato):
    """Un proyecto 'por cotizar' (sin cotización) recibe productos y se ven."""
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    accion = _accion({
        "proyecto_slug": p.slug, "servicio": "Playeras",
        "cantidad": 100, "merma": 5, "proveedor": "Textiles SA",
    })
    EJECUTORES["agregar_producto_proyecto"](accion, admin, {})
    assert accion.entidad_tipo == "producto"
    incluidos = p.productos_incluidos
    assert len(incluidos) == 1
    pp = incluidos[0]
    assert pp.servicio_id == catalogo["serv"].pk
    assert pp.cantidad == 100
    assert pp.merma == 5
    assert pp.proveedor_id == catalogo["prov"].pk


def test_agregar_producto_servicio_inexistente(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    with pytest.raises(ValueError, match="no encontrado"):
        EJECUTORES["agregar_producto_proyecto"](
            _accion({"proyecto_slug": p.slug, "servicio": "no-existe-zzz"}), admin, {})


# ── Toggle de IVA por proveedor (items 1 + 5) ─────────────────────────────────

def test_toggle_iva_por_proveedor(client, proyecto_factory, catalogo, usuario_factory):
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.views import _proveedores_panel
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_diseno")
    ProyectoProducto.objects.create(
        proyecto=p, servicio=catalogo["serv"], cantidad=1,
        costo_unitario=Decimal("1000.00"), proveedor=catalogo["prov"],
        incluir_en_calculo=True)

    # Default: IVA prendido → total_con_iva > total.
    fila = _proveedores_panel(p)[0]
    assert fila["aplica_iva"] is True
    assert fila["total_con_iva"] > fila["total"]

    client.force_login(admin)
    url = reverse("proyectos-proveedor-iva", args=[p.pk, catalogo["prov"].pk])
    resp = client.post(url)
    assert resp.status_code == 200

    # Apagado: sin IVA, total_con_iva == total.
    fila = _proveedores_panel(p)[0]
    assert fila["aplica_iva"] is False
    assert fila["total_con_iva"] == fila["total"]

    # Segundo toggle: vuelve a prender.
    client.post(url)
    assert _proveedores_panel(p)[0]["aplica_iva"] is True


# ── CAPS en cliente vía Chalán (item 8/9) ─────────────────────────────────────

def test_crear_cliente_chalan_uppercase(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.la_cartera.models import Cliente
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"razon_social": "optimist sa de cv"})
    EJECUTORES["crear_cliente"](accion, admin, {})
    c = Cliente.objects.get(pk=accion.entidad_id)
    assert c.razon_social == "OPTIMIST SA DE CV"


# ── Filtro dinero_corto (item 9) ──────────────────────────────────────────────

def test_dinero_corto():
    from cuentas.templatetags.forms_helpers import dinero_corto
    assert dinero_corto(95) == "$95"
    assert dinero_corto(Decimal("95.00")) == "$95"
    assert dinero_corto(Decimal("95.50")) == "$95.50"
    assert dinero_corto(1234) == "$1,234"
