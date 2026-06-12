"""Fixes del chat El Chalán + Tareas (ronda de feedback 2026-06-08).

Cubre: búsqueda por texto en el DSL (op `contiene`), normalización de
filtros dict→lista en consultar_metrica (bug 'gasto en ubers'), fallback de
campos top-level en actualizar_proyecto (bug 'actualizar fecha'), y la página
global de Tareas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


# ── DSL: búsqueda por texto ───────────────────────────────────────────────────


def test_dsl_contiene_filtra_por_texto(centro, usuario_factory):
    from apps.tesoreria.models import Egreso

    from lib.kpi_dsl.ejecutor import ejecutar
    actor = usuario_factory(rol="dueno")
    Egreso.objects.create(monto=Decimal("120.00"), fecha=date.today(),
                          descripcion="Uber al cliente", centro_de_costo=centro, creado_por=actor)
    Egreso.objects.create(monto=Decimal("80.00"), fecha=date.today(),
                          descripcion="UBER aeropuerto", centro_de_costo=centro, creado_por=actor)
    Egreso.objects.create(monto=Decimal("999.00"), fecha=date.today(),
                          descripcion="Papelería", centro_de_costo=centro, creado_por=actor)
    res = ejecutar({
        "entidad": "egreso", "agregacion": "sum", "campo": "monto",
        "ventana_tiempo": "este_mes",
        "filtros": [{"campo": "descripcion", "op": "contiene", "valor": "uber"}],
    }, usuario=None)
    assert res["valor"] == 200.0  # 120 + 80, NO la papelería


def test_consultar_metrica_filtros_dict_se_normaliza(centro, usuario_factory):
    """El bug 'gasto en ubers': filtros como dict {campo:{op,valor}} ahora
    funciona (antes reventaba porque el DSL esperaba lista)."""
    from apps.el_dictado.herramientas import ejecutar_herramienta
    from apps.tesoreria.models import Egreso
    actor = usuario_factory(rol="dueno")
    Egreso.objects.create(monto=Decimal("150.00"), fecha=date.today(),
                          descripcion="Uber juntas", centro_de_costo=centro, creado_por=actor)
    salida = ejecutar_herramienta("consultar_metrica", {
        "entidad": "egreso", "agregacion": "sum", "campo": "monto",
        "ventana_tiempo": "este_mes",
        "filtros": {"descripcion": {"op": "contiene", "valor": "uber"}},
    }, actor)
    assert "error" not in salida
    assert salida["valor"] == 150.0


# ── Ejecutor: actualizar fecha con campos al nivel superior ───────────────────


def test_actualizar_proyecto_fecha_top_level(usuario_factory, cliente_factory):
    """El LLM a veces pone la fecha fuera de `campos`; el fallback la recoge."""
    from apps.el_dictado.ejecutores.basicos import actualizar_proyecto
    from apps.los_proyectos.models import Proyecto
    actor = usuario_factory(rol="dueno")
    cliente = cliente_factory()
    proy = Proyecto.objects.create(nombre="Demo", cliente=cliente, creado_por=actor)
    accion = SimpleNamespace(payload={
        "proyecto_slug": proy.slug,
        "fecha_compromiso": "2026-07-15",  # top-level, NO dentro de campos
    })
    actualizar_proyecto(accion, actor)
    proy.refresh_from_db()
    assert proy.fecha_compromiso is not None
    assert proy.fecha_compromiso.date().isoformat() == "2026-07-15"


# ── Vista global de Tareas ────────────────────────────────────────────────────


def test_tareas_lista_carga(client, usuario_factory, cliente_factory):
    """V6 Bloque 2: /tareas/ es Kanban con default 'mis tareas' — la tarea
    debe estar asignada al actor para aparecer sin filtros."""
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import Proyecto
    actor = usuario_factory(rol="dueno")
    cliente = cliente_factory()
    proy = Proyecto.objects.create(nombre="Proy", cliente=cliente, creado_por=actor)
    Tarea.objects.create(proyecto=proy, titulo="Revisar arte", estado="pendiente",
                         creado_por=actor, asignada_a=actor)
    client.force_login(actor)
    resp = client.get("/tareas/")
    assert resp.status_code == 200
    assert b"Revisar arte" in resp.content
    # La vista de lista tabular sigue viva en /tareas/lista/.
    assert client.get("/tareas/lista/").status_code == 200
