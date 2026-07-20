"""Sprint Fiscal y Estructura 2026-07.

Cubre los puntos de refactor del modelo de datos del catálogo:

- #12 Unidad consolidada a 'pz' (sin selector/columna; forms sin `unidad`).
- #10 Estado «Disponible» jubilado de la UI (sin columna/badge/toggle), pero
  el archivado (`activo`) se conserva.
- #8  «Variaciones» → bitácora de «Usos» (historial real desde proyectos).
- #9  Columna «Usos» en la tabla del catálogo.

El caso fiscal (retención de IVA nominal) vive en test_resico_honorarios.py.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    return cat


# ── #12 Unidad consolidada a 'pz' ────────────────────────────────────────────

def test_servicio_form_sin_unidad_ni_activo():
    from apps.el_catalogo.forms import ServicioForm
    campos = set(ServicioForm().fields)
    assert "unidad" not in campos
    assert "activo" not in campos  # #10: «Disponible» fuera del form


def test_item_forms_sin_unidad():
    from apps.cotizaciones.forms import CotizacionItemForm
    from apps.facturacion.forms import FacturaItemForm
    assert "unidad" not in set(CotizacionItemForm().fields)
    assert "unidad" not in set(FacturaItemForm().fields)


def test_servicio_nuevo_nace_en_pz(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/catalogo/nuevo", {
        "nombre": "Playera", "precio_base": "100.00", "categoria": categoria.pk,
        "descripcion_default": "",
    })
    assert resp.status_code == 302
    srv = Servicio.objects.get(nombre="Playera")
    assert srv.unidad == "pz"


# ── #9/#10/#12 columnas de la tabla del catálogo ─────────────────────────────

def test_lista_catalogo_columnas(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    Servicio.objects.create(nombre="Logo", precio_base="1500.00", categoria=categoria)
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get("/catalogo/").content.decode()
    # #9 columna Usos (badge por fila con su tooltip; Sprint 2 UX quitó el link
    # de texto «Usos» del renglón — la fila entera navega al panel de edición).
    assert "Usos" in html
    assert "Veces que se ha usado en proyectos" in html
    assert ">Unidad<" not in html      # #12 sin columna Unidad
    assert ">Estado<" not in html      # #10 sin columna Estado
    assert "Disponible" not in html    # #10 sin badge Disponible


# ── #10 archivar se conserva ─────────────────────────────────────────────────

def test_archivar_producto_sigue_funcionando(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Archivable", precio_base="50.00", categoria=categoria)
    client.force_login(usuario_factory(rol="super_admin"))
    client.post(f"/catalogo/{srv.pk}/archivar")
    srv.refresh_from_db()
    assert srv.activo is False


# ── #8 Variaciones → Usos (historial) ────────────────────────────────────────

def test_pagina_usos_muestra_historial(client, usuario_factory, categoria, proyecto_factory):
    from apps.el_catalogo.models import Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.models.proceso import ProyectoProductoProceso

    srv = Servicio.objects.create(nombre="Playera bordada", precio_base="200.00",
                                  costo="80.00", categoria=categoria)
    prov = Proveedor.objects.create(razon_social="Bordados Don José")
    proy = proyecto_factory(nombre="Campaña verano")
    pp = ProyectoProducto.objects.create(
        proyecto=proy, servicio=srv, proveedor=prov, cantidad=50,
        precio_unitario=Decimal("220.00"), costo_unitario=Decimal("90.00"),
    )
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=prov, costo=Decimal("15.00"), por_pieza=True,
    )

    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/catalogo/{srv.pk}/usos/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Campaña verano" in html          # el proyecto donde se usó
    assert "Bordados Don José" in html        # el proveedor
    assert "Usos del producto" in html        # subtítulo de la bitácora


def test_usos_vacio_muestra_empty_state(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Sin usar", precio_base="10.00", categoria=categoria)
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/catalogo/{srv.pk}/usos/")
    assert resp.status_code == 200
    assert "Sin usos todav" in resp.content.decode()


def test_variaciones_url_retirada():
    """La URL vieja `catalogo-variaciones` ya no existe (#8)."""
    from django.urls import NoReverseMatch, reverse
    with pytest.raises(NoReverseMatch):
        reverse("catalogo-variaciones", args=[1])
