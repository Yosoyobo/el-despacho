"""Cuando cambia el costo del catálogo, ¿qué pasa con los proyectos?

LC 2026-08-12 (Oscar): «cuando actualice en la pág. de un producto de Simil
sus números en su calculadora interna, esto se debe de actualizar solito y
automáticamente a las instancias donde está contabilizado en proyectos».

Decisión suya: **se actualizan sólo los vivos**. Lo que ya se pagó o se
facturó NO se toca — mover un costo hacia atrás descuadra la contabilidad y
cambia márgenes históricos que ya se reportaron.

Una línea se actualiza si TODO esto se cumple:

* el proyecto no está archivado ni en un estado terminal;
* la línea no generó un egreso (si lo generó, ese dinero ya salió);
* el proyecto no tiene una cotización pagada;
* y el costo de la línea **coincidía con el costo anterior del catálogo**, es
  decir nadie lo escribió a mano para ese proyecto. Un costo negociado
  aparte es una decisión, no una copia que haya que refrescar.

Nunca lanza: si algo falla, se guarda el producto igual y no se propaga.
"""

from __future__ import annotations

from decimal import Decimal

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def propagar_costo(servicio, costo_anterior, actor=None) -> int:
    """Escribe el costo nuevo en las líneas vivas. Devuelve cuántas cambiaron."""
    try:
        return _propagar(servicio, costo_anterior, actor)
    except Exception:  # noqa: BLE001 — guardar el producto manda; esto es extra
        return 0


def _propagar(servicio, costo_anterior, actor) -> int:
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.models.estado import EstadoProyecto

    nuevo = Decimal(str(servicio.costo or 0))
    anterior = Decimal(str(costo_anterior or 0))
    if nuevo == anterior:
        return 0

    terminales = list(
        EstadoProyecto.objects.filter(terminal=True).values_list("slug", flat=True)
    )
    lineas = (
        ProyectoProducto.objects.filter(servicio=servicio)
        .exclude(proyecto__archivado=True)
        .exclude(proyecto__estado__in=terminales)
        .filter(egreso__isnull=True)
        .select_related("proyecto")
    )

    tocadas = []
    for linea in lineas:
        # Vacío = ya venía heredando del catálogo; igual al anterior = era una
        # copia del catálogo, no un costo negociado para ese proyecto.
        heredaba = linea.costo_unitario is None or Decimal(str(linea.costo_unitario)) == anterior
        if not heredaba or _tiene_cotizacion_pagada(linea.proyecto):
            continue
        linea.costo_unitario = nuevo
        linea.costo_unitario_expr = ""
        tocadas.append(linea)

    if not tocadas:
        return 0
    ProyectoProducto.objects.bulk_update(tocadas, ["costo_unitario", "costo_unitario_expr"])
    emitir(EventoPortavoz(
        tipo="catalogo.costo_propagado",
        actor_id=getattr(actor, "pk", None),
        actor_email=getattr(actor, "email", ""),
        payload={
            "servicio_id": servicio.pk,
            "costo_anterior": str(anterior),
            "costo_nuevo": str(nuevo),
            "lineas": len(tocadas),
            "proyectos": sorted({linea.proyecto_id for linea in tocadas}),
        },
    ))
    return len(tocadas)


def _tiene_cotizacion_pagada(proyecto) -> bool:
    try:
        return proyecto.cotizaciones.filter(estado="pagada").exists()
    except Exception:  # noqa: BLE001 — sin cotizaciones se sigue de frente
        return False
