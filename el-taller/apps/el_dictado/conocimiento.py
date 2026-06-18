"""Inyección del conocimiento de negocio aprobado en los prompts del Chalán.

El conocimiento `activo` (aprobado por el super_admin) se antepone como bloque
`[CONTEXTO DEL NEGOCIO]` al system prompt del chat y del análisis proactivo,
para que las opiniones del Chalán estén fundamentadas en lo que ha aprendido
del negocio. Solo se inyecta lo aprobado (review-first) y con `peso_efectivo`
sobre el umbral. Defensivo: cualquier fallo → bloque vacío.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

UMBRAL = 0.3
TOPE = 15


def conocimiento_negocio_activo(ambito: str | None = None) -> list[dict]:
    """Top observaciones activas (opcionalmente de un ámbito), por peso."""
    try:
        from .models import ConocimientoNegocio
        qs = ConocimientoNegocio.objects.filter(activo=True)
        if ambito:
            qs = qs.filter(ambito=ambito)
        items = [
            {"ambito": c.ambito, "observacion": c.observacion, "peso": c.peso_efectivo()}
            for c in qs[:60]
        ]
        items = [i for i in items if i["peso"] >= UMBRAL]
        items.sort(key=lambda i: i["peso"], reverse=True)
        return items[:TOPE]
    except Exception:  # noqa: BLE001
        logger.warning("conocimiento_negocio_activo falló", exc_info=True)
        return []


def bloque_contexto_negocio(ambito: str | None = None) -> str:
    """Bloque de texto `[CONTEXTO DEL NEGOCIO]` para anteponer al prompt.

    Vacío ("") si no hay conocimiento aprobado — degradación limpia.
    """
    items = conocimiento_negocio_activo(ambito)
    if not items:
        return ""
    lineas = ["[CONTEXTO DEL NEGOCIO — lo que el Chalán sabe del despacho]"]
    for i in items:
        lineas.append(f"- ({i['ambito']}) {i['observacion']}")
    lineas.append("[FIN CONTEXTO DEL NEGOCIO]")
    return "\n".join(lineas)
