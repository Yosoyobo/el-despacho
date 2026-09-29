"""Cada campo que el DSL de KPIs custom deja usar existe en su modelo.

`lib/kpi_dsl/schema.py` es una whitelist escrita a mano: si nombra un campo
que el modelo no tiene, el validador lo acepta y el ORM truena con
`FieldError` al previsualizar o al pintar el KPI (un 500). Pasó con
`tarea.creada_por` (el modelo dice `creado_por`), `proyecto.tipo` y
`cliente.archivado` (el modelo dice `activo`).

v2: se revisan TODAS las rutas (campos filtrables/agregables con su `ruta`,
agrupaciones, extremos de cada duración, autor/asignado, catálogos) y que el
TIPO declarado corresponda al campo real (un «dinero» que no es decimal, una
«fecha» que no es fecha o una duración entre campos que no son fechas
calcularían basura sin tronar).
"""

from __future__ import annotations

import pytest
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from lib.kpi_dsl.schema import ENTIDADES, TIPOS_CAMPO, ruta_de


def _campo_final(modelo, ruta: str):
    """Sigue `a__b__c` por las relaciones, como lo haría un filtro del ORM.
    Devuelve el campo del final o None si algún tramo no existe."""
    actual = modelo
    partes = ruta.split("__")
    campo = None
    for i, parte in enumerate(partes):
        try:
            campo = actual._meta.get_field(parte)
        except FieldDoesNotExist:
            return None
        if i < len(partes) - 1:
            if not campo.is_relation:
                return None
            actual = campo.related_model
    return campo


def _resuelve(modelo, ruta: str) -> bool:
    return _campo_final(modelo, ruta) is not None


def _rutas(entidad: str, spec: dict) -> list[tuple[str, str]]:
    rutas = [(f"campo {c}", ruta_de(entidad, c)) for c in spec["campos"]]
    rutas += [("numérico", ruta_de(entidad, c)) for c in spec["campos_numericos"]]
    rutas += [("filtrable", ruta_de(entidad, c)) for c in spec["campos_filtrables"]]
    rutas += [(f"agrupación {g}", s["ruta"]) for g, s in spec["agrupaciones"].items()]
    for d, s in spec["duraciones"].items():
        rutas += [(f"duración {d}", ruta_de(entidad, s["desde"])),
                  (f"duración {d}", ruta_de(entidad, s["hasta"]))]
    rutas.append(("fecha", ruta_de(entidad, spec["campo_fecha"])))
    for rol in ("campo_autor", "campo_asignado"):
        if spec.get(rol):
            rutas.append((rol, spec[rol]))
    return rutas


@pytest.mark.parametrize("entidad", sorted(ENTIDADES))
def test_los_campos_de_la_entidad_existen_en_el_modelo(entidad):
    spec = ENTIDADES[entidad]
    modelo = apps.get_model(spec["modelo"])
    rotos = [f"{uso}:{ruta}" for uso, ruta in _rutas(entidad, spec) if not _resuelve(modelo, ruta)]
    assert not rotos, f"{entidad} ({spec['modelo']}) no tiene: {rotos}"


_TIPO_A_CAMPOS = {
    "dinero": (models.DecimalField,),
    "numero": (models.IntegerField, models.DecimalField, models.FloatField),
    "fecha": (models.DateField,),  # DateTimeField hereda de DateField
    "booleano": (models.BooleanField,),
    "texto": (models.CharField, models.TextField),
    "opcion": (models.CharField,),
    "relacion": (models.ForeignKey, models.OneToOneField),
}


@pytest.mark.parametrize("entidad", sorted(ENTIDADES))
def test_el_tipo_declarado_es_el_del_modelo(entidad):
    spec = ENTIDADES[entidad]
    modelo = apps.get_model(spec["modelo"])
    malos = []
    for c, s in spec["campos"].items():
        assert s["tipo"] in TIPOS_CAMPO, f"{entidad}.{c}: tipo {s['tipo']!r} desconocido"
        campo = _campo_final(modelo, ruta_de(entidad, c))
        if campo is None or not isinstance(campo, _TIPO_A_CAMPOS[s["tipo"]]):
            malos.append(f"{c}:{s['tipo']}≠{type(campo).__name__}")
        # Un «opcion» sin choices necesita su catálogo (si no, el formulario no
        # tiene qué ofrecer).
        if s["tipo"] == "opcion" and campo is not None and not campo.choices:
            assert s.get("catalogo"), f"{entidad}.{c} es opción sin choices ni catálogo"
    assert not malos, f"{entidad}: {malos}"


@pytest.mark.parametrize("entidad", sorted(ENTIDADES))
def test_cada_duracion_va_entre_dos_fechas_declaradas(entidad):
    spec = ENTIDADES[entidad]
    for d, s in spec["duraciones"].items():
        for extremo in (s["desde"], s["hasta"]):
            assert extremo in spec["campos"], f"{entidad}.{d}: {extremo} no es campo del schema"
            assert spec["campos"][extremo]["tipo"] == "fecha", f"{entidad}.{d}: {extremo} no es fecha"
        assert s["unidad"] in ("dias", "horas", "minutos")


@pytest.mark.parametrize("entidad", sorted(ENTIDADES))
def test_la_fecha_de_la_ventana_es_una_fecha_del_schema(entidad):
    spec = ENTIDADES[entidad]
    assert spec["campos"][spec["campo_fecha"]]["tipo"] == "fecha"


def test_los_catalogos_existen_y_tienen_slug_y_label():
    for entidad, spec in ENTIDADES.items():
        for c, s in spec["campos"].items():
            if s.get("catalogo"):
                Catalogo = apps.get_model(s["catalogo"])
                for campo in ("slug", "label", "orden"):
                    assert _resuelve(Catalogo, campo), f"{entidad}.{c}: {s['catalogo']} sin {campo}"


def test_los_permisos_son_del_catalogo():
    """Cada permiso nombrado existe en `CATALOGO_PERMISOS` (§4 #20)."""
    from lib.permisos_defaults import CATALOGO_PERMISOS

    def existe(p: str) -> bool:
        modulo, accion = p.split(".", 1)
        return accion in (CATALOGO_PERMISOS.get(modulo) or ())

    for entidad, spec in ENTIDADES.items():
        for p in (*spec["permiso"], *spec["permiso_mio"]):
            assert existe(p), f"{entidad}: permiso {p} no está en el catálogo"
        for c, s in spec["campos"].items():
            for p in s.get("permiso", ()):
                assert existe(p), f"{entidad}.{c}: permiso {p} no está en el catálogo"


def test_el_candado_ve_un_campo_inventado():
    # Si esto pasara, el candado aprobaría cualquier cosa.
    assert not _resuelve(apps.get_model("pizarron.Tarea"), "creada_por")
    assert _resuelve(apps.get_model("pizarron.Tarea"), "creado_por")
    assert not _resuelve(apps.get_model("pizarron.Mandado"), "runner")
    assert _resuelve(apps.get_model("pizarron.Mandado"), "tarea__runner")
