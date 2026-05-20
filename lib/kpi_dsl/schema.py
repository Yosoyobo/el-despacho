"""Whitelists del DSL — todo lo NO listado aquí queda prohibido."""

from __future__ import annotations

# Cada entrada describe: modelo Django (path lazy), campos numéricos
# permitidos para sum/avg/min/max, campos filtrables, campo de fecha que
# usan las ventanas_tiempo, link sugerido para el "Ver más".
ENTIDADES: dict[str, dict] = {
    "proyecto": {
        "modelo": "proyectos.Proyecto",
        "campos_numericos": ("monto_cotizado",),
        "campos_filtrables": {
            "estado": ("eq", "in"),
            "tipo": ("eq", "in"),
        },
        "campo_fecha": "creado_en",
        "link_default": "/proyectos/",
        "campo_autor": None,
        "campo_asignado": "asignaciones__usuario",
    },
    "tarea": {
        "modelo": "pizarron.Tarea",
        "campos_numericos": (),
        "campos_filtrables": {
            "estado": ("eq", "in"),
            "prioridad": ("eq", "in"),
        },
        "campo_fecha": "creado_en",
        "link_default": "/pizarron/",
        "campo_autor": "creada_por",
        "campo_asignado": "asignada_a",
    },
    "cliente": {
        "modelo": "cartera.Cliente",
        "campos_numericos": (),
        "campos_filtrables": {
            "archivado": ("eq",),
        },
        "campo_fecha": "creado_en",
        "link_default": "/cartera/",
        "campo_autor": None,
        "campo_asignado": None,
    },
    "egreso": {
        "modelo": "tesoreria.Egreso",
        "campos_numericos": ("monto",),
        "campos_filtrables": {
            "estado_pago": ("eq", "in"),
            "metodo": ("eq", "in"),
            "anulado": ("eq",),
        },
        "campo_fecha": "fecha",
        "link_default": "/tesoreria/egresos/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
    },
    "ingreso": {
        "modelo": "tesoreria.Ingreso",
        "campos_numericos": ("monto",),
        "campos_filtrables": {
            "anulado": ("eq",),
        },
        "campo_fecha": "fecha",
        "link_default": "/tesoreria/ingresos/",
        "campo_autor": "creado_por",
        "campo_asignado": None,
    },
    "recado": {
        "modelo": "recados.Recado",
        "campos_numericos": (),
        "campos_filtrables": {},
        "campo_fecha": "creado_en",
        "link_default": "/recados/legacy/",
        "campo_autor": "autor",
        "campo_asignado": None,
    },
    "buzon_mensaje": {
        "modelo": "buzon.MensajeBuzon",
        "campos_numericos": (),
        "campos_filtrables": {
            "tipo": ("eq", "in"),
            "estado": ("eq", "in"),
        },
        "campo_fecha": "creado_en",
        "link_default": "/buzon/",
        "campo_autor": "autor",
        "campo_asignado": None,
    },
}

AGREGACIONES = ("count", "sum", "avg", "min", "max")
OPS_FILTRO = ("eq", "in", "gte", "lte", "gt", "lt")

# Token → función que retorna (date_inicio, date_fin) o None=sin filtro.
VENTANAS_TIEMPO = ("siempre", "ultimos_7d", "ultimos_30d", "este_mes", "este_ano")

ALCANCES_USUARIO = ("todos", "mio")
