"""Ejecuta un DSL validado contra el ORM de Django con cost guards.

Cost guards aplicados:
- Slice a `MAX_FILAS_PRE_AGREGACION` filas antes de Sum/Avg/Min/Max
  (count es ya O(1) en SQL — no se limita).
- Construye el queryset por whitelist, nunca aceptando atributos crudos.
- Logs/errores ASCII para no romper en cualquier locale.

NO usa `signal.SIGALRM` para timeout porque no es portable a Windows
ni seguro en threads. El slice cumple el rol práctico de cost guard
(en el datatablo del despacho los modelos no pasan de ~10k filas).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from django.apps import apps
from django.db.models import Avg, Max, Min, Sum
from django.utils import timezone

from .schema import ENTIDADES
from .validador import ValidacionError, validar

logger = logging.getLogger(__name__)

MAX_FILAS_PRE_AGREGACION = 10_000


def _modelo_django(entidad: str):
    app_label, model_name = ENTIDADES[entidad]["modelo"].split(".", 1)
    return apps.get_model(app_label, model_name)


def _ventana_a_rango(ventana: str) -> tuple[date | None, date | None]:
    hoy = timezone.localdate()
    if ventana == "siempre":
        return None, None
    if ventana == "ultimos_7d":
        return hoy - timedelta(days=7), hoy
    if ventana == "ultimos_30d":
        return hoy - timedelta(days=30), hoy
    if ventana == "este_mes":
        return hoy.replace(day=1), hoy
    if ventana == "este_ano":
        return hoy.replace(month=1, day=1), hoy
    return None, None


def _aplicar_filtros(qs, filtros: list[dict]):
    op_a_lookup = {
        "eq": "exact",
        "in": "in",
        "gte": "gte",
        "lte": "lte",
        "gt": "gt",
        "lt": "lt",
        "contiene": "icontains",
    }
    for f in filtros:
        lookup = op_a_lookup[f["op"]]
        clave = f"{f['campo']}__{lookup}" if lookup != "exact" else f["campo"]
        qs = qs.filter(**{clave: f["valor"]})
    return qs


def _aplicar_ventana(qs, entidad: str, ventana: str):
    from django.db.models import DateTimeField

    campo_fecha = ENTIDADES[entidad].get("campo_fecha")
    if not campo_fecha or ventana == "siempre":
        return qs
    desde, hasta = _ventana_a_rango(ventana)
    # El lookup `__date` SOLO aplica a DateTimeField. Egreso/Ingreso usan
    # `fecha` como DateField puro — ahí va el lookup directo (sin `__date`),
    # o Django lanza "Unsupported lookup 'date' for DateField".
    try:
        es_datetime = isinstance(qs.model._meta.get_field(campo_fecha), DateTimeField)
    except Exception:  # noqa: BLE001
        es_datetime = True
    sufijo = "__date" if es_datetime else ""
    if desde:
        qs = qs.filter(**{f"{campo_fecha}{sufijo}__gte": desde})
    if hasta:
        qs = qs.filter(**{f"{campo_fecha}{sufijo}__lte": hasta})
    return qs


def _aplicar_alcance(qs, entidad: str, alcance_usuario: str, usuario):
    if alcance_usuario != "mio" or usuario is None:
        return qs
    cfg = ENTIDADES[entidad]
    if cfg["campo_autor"]:
        return qs.filter(**{cfg["campo_autor"]: usuario})
    if cfg["campo_asignado"]:
        return qs.filter(**{cfg["campo_asignado"]: usuario}).distinct()
    return qs


def _formatear_valor(valor: Any, agregacion: str) -> Any:
    if valor is None:
        return 0
    if agregacion == "count":
        return int(valor)
    # Sum/Avg pueden devolver Decimal — convertir a float redondeado.
    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return valor


def ejecutar(definicion: dict, *, usuario=None, validado: bool = False) -> dict:
    """Ejecuta una definición DSL. Si `validado=False`, la valida primero.

    Retorna `{valor, nota, link}` con la misma forma que los KPIs del catálogo.
    En caso de ValidacionError la deja propagar (el caller decide si la
    captura como 'error'). En caso de error transitorio del ORM, devuelve
    `{valor: '?', nota: 'error', link: ...}` y loggea.
    """
    if not validado:
        definicion = validar(definicion)

    entidad = definicion["entidad"]
    cfg = ENTIDADES[entidad]
    Modelo = _modelo_django(entidad)
    qs = Modelo._default_manager.all()
    qs = _aplicar_filtros(qs, definicion["filtros"])
    qs = _aplicar_ventana(qs, entidad, definicion["ventana_tiempo"])
    qs = _aplicar_alcance(qs, entidad, definicion["alcance_usuario"], usuario)

    agregacion = definicion["agregacion"]
    try:
        if agregacion == "count":
            valor = qs.count()
        else:
            # Cost guard: nunca agregamos sobre más de MAX_FILAS_PRE_AGREGACION.
            # PKs limitados → re-filtramos por __in para preservar SQL-level agg.
            pks_truncados = list(qs.order_by("-pk").values_list("pk", flat=True)[:MAX_FILAS_PRE_AGREGACION])
            qs_truncado = Modelo._default_manager.filter(pk__in=pks_truncados)
            agg_fn = {"sum": Sum, "avg": Avg, "min": Min, "max": Max}[agregacion]
            valor = qs_truncado.aggregate(v=agg_fn(definicion["campo"]))["v"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("kpi_dsl ejecutar falló entidad=%s agg=%s: %s", entidad, agregacion, exc)
        return {"valor": "?", "nota": "error", "link": cfg["link_default"]}

    nota = ""
    if agregacion != "count":
        total_filas = qs.count()
        if total_filas > MAX_FILAS_PRE_AGREGACION:
            nota = f"sobre {MAX_FILAS_PRE_AGREGACION} más recientes (de {total_filas})"
    return {
        "valor": _formatear_valor(valor, agregacion),
        "nota": nota,
        "link": cfg["link_default"],
    }


def ejecutar_con_preview(definicion: dict, *, usuario=None) -> dict:
    """Variante para el flujo de creación — devuelve también detalles de debug."""
    try:
        normalizada = validar(definicion)
    except ValidacionError as exc:
        return {"ok": False, "error": str(exc)}
    resultado = ejecutar(normalizada, usuario=usuario, validado=True)
    return {"ok": True, "resultado": resultado, "definicion_normalizada": normalizada}
