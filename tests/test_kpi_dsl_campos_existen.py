"""Cada campo que el DSL de KPIs custom deja usar existe en su modelo.

`lib/kpi_dsl/schema.py` es una whitelist escrita a mano: si nombra un campo
que el modelo no tiene, el validador lo acepta y el ORM truena con
`FieldError` al previsualizar o al pintar el KPI (un 500). Pasó con
`tarea.creada_por` (el modelo dice `creado_por`), `proyecto.tipo` y
`cliente.archivado` (el modelo dice `activo`).
"""

from __future__ import annotations

import pytest
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist

from lib.kpi_dsl.schema import ENTIDADES


def _resuelve(modelo, ruta: str) -> bool:
    """Sigue `a__b__c` por las relaciones, como lo haría un filtro del ORM."""
    actual = modelo
    for i, parte in enumerate(ruta.split("__")):
        try:
            campo = actual._meta.get_field(parte)
        except FieldDoesNotExist:
            return False
        if i < len(ruta.split("__")) - 1:
            if not campo.is_relation:
                return False
            actual = campo.related_model
    return True


def _rutas(spec: dict) -> list[tuple[str, str]]:
    rutas = [("numérico", c) for c in spec["campos_numericos"]]
    rutas += [("filtrable", c) for c in spec["campos_filtrables"]]
    rutas.append(("fecha", spec["campo_fecha"]))
    for rol in ("campo_autor", "campo_asignado"):
        if spec.get(rol):
            rutas.append((rol, spec[rol]))
    return rutas


@pytest.mark.parametrize("entidad", sorted(ENTIDADES))
def test_los_campos_de_la_entidad_existen_en_el_modelo(entidad):
    spec = ENTIDADES[entidad]
    modelo = apps.get_model(spec["modelo"])
    rotos = [f"{uso}:{ruta}" for uso, ruta in _rutas(spec) if not _resuelve(modelo, ruta)]
    assert not rotos, f"{entidad} ({spec['modelo']}) no tiene: {rotos}"


def test_el_candado_ve_un_campo_inventado():
    # Si esto pasara, el candado aprobaría cualquier cosa.
    assert not _resuelve(apps.get_model("pizarron.Tarea"), "creada_por")
    assert _resuelve(apps.get_model("pizarron.Tarea"), "creado_por")
