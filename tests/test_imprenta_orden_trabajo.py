"""La orden de trabajo (ticket 15 de Oscar, 2026-10-14).

    «En la orden de trabajo generada, genial, sólo en los proveedores quiero que
    incluya los de impresión etc, la fecha de entrega en lenguaje completo,
    lunes 1 de diciembre de 2025.»

Dos cambios:

1. **Proveedores**: la columna decía sólo el del producto. Ahora trae también los
   de impresión y los de otros procesos, cada uno con su rol y sin repetirse.
2. **Fecha**: «lunes 1 de diciembre de 2025», con los nombres de `lib.fecha` (que
   no dependen del idioma del servidor).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

MX = ZoneInfo("America/Mexico_City")


@pytest.fixture(autouse=True)
def _sin_cache():
    from imprenta import config

    config.olvidar()
    yield
    config.olvidar()


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def entorno(proyecto_factory, cliente_factory, jefe):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto, ProyectoProductoProceso

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    base = Proveedor.objects.create(razon_social="Crea Blanks", activo=True)
    bordados = Proveedor.objects.create(razon_social="Bordados Mx", activo=True)
    sublima = Proveedor.objects.create(razon_social="Sublima Pro", activo=True)
    srv = Servicio.objects.create(nombre="Gorra", precio_base="195", costo="80", categoria=cat)
    cli = cliente_factory(creado_por=jefe, razon_social="Heladería Sur")
    p = proyecto_factory(
        nombre="Feria", cliente=cli, creado_por=jefe,
        fecha_compromiso=dt.datetime(2025, 12, 1, 12, 0, tzinfo=MX))
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, proveedor=base, cantidad=70,
        precio_unitario=Decimal("195.00"), costo_unitario=Decimal("80.00"),
        incluir_en_calculo=True)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", proveedor=bordados, costo=Decimal("12"), orden=1)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", proveedor=sublima, descripcion="Sublimado",
        costo=Decimal("5"), orden=2)
    return {"p": p, "pp": pp, "base": base, "bordados": bordados, "sublima": sublima}


def _ot(client, jefe, p):
    client.force_login(jefe)
    return client.get(reverse("imprenta:ver", args=["orden_trabajo", p.pk])).content.decode()


# ── Proveedores ──────────────────────────────────────────────────────────────

def test_la_ot_lista_tambien_los_proveedores_de_impresion_y_de_procesos(client, jefe, entorno):
    html = _ot(client, jefe, entorno["p"])

    assert "Crea Blanks" in html
    assert "Bordados Mx" in html and "(impresión)" in html
    assert "Sublima Pro" in html and "(proceso)" in html
    # Con más de uno, el del producto también dice qué es.
    assert "(producto)" in html


def test_un_proveedor_que_hace_dos_cosas_sale_una_sola_vez(entorno):
    from apps.los_proyectos.models import ProyectoProductoProceso

    from imprenta.documentos.proyectos import proveedores_de_la_linea

    # Crea Blanks además imprime.
    ProyectoProductoProceso.objects.create(
        producto=entorno["pp"], tipo="impresion", proveedor=entorno["base"], costo=1, orden=3)
    procesos = list(entorno["pp"].procesos.select_related("proveedor").order_by("orden", "pk"))

    lista = proveedores_de_la_linea(entorno["pp"], procesos)

    nombres = [x["nombre"] for x in lista]
    assert nombres.count("Crea Blanks") == 1
    assert nombres[0] == "Crea Blanks", "el del producto va primero"
    assert next(x for x in lista if x["nombre"] == "Crea Blanks")["roles"] == ["producto", "impresión"]


def test_con_un_solo_proveedor_de_producto_no_se_rotula(client, jefe, proyecto_factory,
                                                         cliente_factory):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    prov = Proveedor.objects.create(razon_social="Solo Uno", activo=True)
    srv = Servicio.objects.create(nombre="Taza", precio_base="10", categoria=cat)
    p = proyecto_factory(nombre="Simple", creado_por=jefe, cliente=cliente_factory(creado_por=jefe))
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, proveedor=prov, cantidad=5,
                                    incluir_en_calculo=True)

    html = _ot(client, jefe, p)

    assert "Solo Uno" in html and "(producto)" not in html


def test_el_proveedor_de_impresion_sale_aunque_el_bloque_procesos_este_apagado(
        client, jefe, entorno):
    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="orden_trabajo", valores={"bloque_procesos": False})

    html = _ot(client, jefe, entorno["p"])

    assert "Bordados Mx" in html
    assert "· Impresión" not in html, "el bloque Procesos apagado sigue apagado"


def test_apagado_el_bloque_de_proveedores_no_sale_ninguno(client, jefe, entorno):
    from imprenta.models import AjusteImprenta

    AjusteImprenta.objects.create(ambito="orden_trabajo", valores={"bloque_proveedores": False})
    html = _ot(client, jefe, entorno["p"])
    # El bloque «Procesos» sigue diciendo con quién se hace cada proceso; lo que
    # se apaga es la COLUMNA de proveedores (y sus roles) y la línea de «otros».
    assert "(proceso)" not in html and "(impresión)" not in html
    assert "Otros proveedores" not in html and "Crea Blanks" not in html


def test_los_proveedores_del_proyecto_que_ninguna_linea_nombra_van_aparte(client, jefe, entorno):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProveedor

    flete = Proveedor.objects.create(razon_social="Fletes Rápidos", activo=True)
    ProyectoProveedor.objects.create(proyecto=entorno["p"], proveedor=flete)
    # Éste ya sale en una línea: no se repite abajo.
    ProyectoProveedor.objects.create(proyecto=entorno["p"], proveedor=entorno["bordados"])

    html = _ot(client, jefe, entorno["p"])

    assert "Otros proveedores del proyecto: Fletes Rápidos (ellos nos entregan)." in html


def test_la_ot_sigue_sin_precios(client, jefe, entorno):
    html = _ot(client, jefe, entorno["p"])
    assert "$195" not in html and "$80" not in html


# ── Fecha ────────────────────────────────────────────────────────────────────

def test_la_fecha_de_entrega_va_con_todas_sus_letras(client, jefe, entorno):
    html = _ot(client, jefe, entorno["p"])

    assert "lunes 1 de diciembre de 2025" in html
    assert "01/12/2025" not in html


def test_a_las_once_de_la_noche_sigue_siendo_el_mismo_dia(client, jefe, entorno):
    """En la base queda en UTC (ya es martes 2); el documento es de México."""
    from apps.los_proyectos.models import Proyecto

    Proyecto.objects.filter(pk=entorno["p"].pk).update(
        fecha_compromiso=dt.datetime(2025, 12, 1, 23, 30, tzinfo=MX))

    assert "lunes 1 de diciembre de 2025" in _ot(client, jefe, entorno["p"])


def test_fecha_larga_en_espanol_sin_depender_del_servidor():
    from lib.fecha import fecha_larga

    assert fecha_larga(dt.date(2025, 12, 1)) == "lunes 1 de diciembre de 2025"
    assert fecha_larga(dt.date(2026, 3, 4)) == "miércoles 4 de marzo de 2026"
    assert fecha_larga(dt.date(2026, 9, 5)) == "sábado 5 de septiembre de 2026"
    assert fecha_larga(dt.date(2025, 12, 1), con_dia=False) == "1 de diciembre de 2025"
    assert fecha_larga("2025-12-01") == "lunes 1 de diciembre de 2025"
    assert fecha_larga(dt.datetime(2025, 12, 2, 5, 30, tzinfo=dt.UTC)) == "lunes 1 de diciembre de 2025"
    assert fecha_larga(dt.datetime(2025, 12, 1, 8, 0)) == "lunes 1 de diciembre de 2025"


def test_fecha_larga_con_basura_devuelve_vacio():
    from lib.fecha import fecha_larga

    for malo in (None, "", "no es fecha", 5, "2025-13-45"):
        assert fecha_larga(malo) == "", malo


def test_fecha_larga_no_depende_del_idioma_activo():
    from django.utils import translation

    from lib.fecha import fecha_larga

    with translation.override("en"):
        assert fecha_larga(dt.date(2025, 12, 1)) == "lunes 1 de diciembre de 2025"
