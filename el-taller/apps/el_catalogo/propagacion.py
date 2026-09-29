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

**El proveedor ★ (LC 2026-09-28, Oscar).** Cambiar el proveedor principal del
producto NO se aplica solo: «preguntar al guardar». La ficha abre un modal con
las líneas donde el cambio tiene sentido —todas marcadas, desmarcables— y sólo
las que el usuario deja marcadas cambian. Son las mismas líneas VIVAS del costo
(proyecto no archivado ni terminal, línea sin egreso, proyecto sin cotización
pagada) y, en lugar de «el costo coincidía», que **su proveedor ERA el principal
anterior**: si alguien le puso otro proveedor a mano para ese proyecto, eso es
una decisión, no una copia que refrescar.
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


def _lineas_vivas(servicio):
    """Las líneas de este producto que todavía se pueden tocar: proyecto no
    archivado ni en estado terminal, y la línea sin egreso (ese dinero ya salió).

    La regla de la cotización pagada no cabe en SQL limpio (la consultan los que
    llaman, línea por línea), así que aquí no va."""
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.models.estado import EstadoProyecto

    terminales = list(
        EstadoProyecto.objects.filter(terminal=True).values_list("slug", flat=True)
    )
    return (
        ProyectoProducto.objects.filter(servicio=servicio)
        .exclude(proyecto__archivado=True)
        .exclude(proyecto__estado__in=terminales)
        .filter(egreso__isnull=True)
        .select_related("proyecto")
    )


def _propagar(servicio, costo_anterior, actor) -> int:
    from apps.los_proyectos.models import ProyectoProducto

    nuevo = Decimal(str(servicio.costo or 0))
    anterior = Decimal(str(costo_anterior or 0))
    if nuevo == anterior:
        return 0

    lineas = _lineas_vivas(servicio)

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


# ── El proveedor ★ ───────────────────────────────────────────────────────────

def lineas_para_proveedor(servicio, anterior_id) -> list:
    """Las líneas que ofrecería el modal «¿También en estos proyectos?».

    Vivas (ver `_lineas_vivas`), sin cotización pagada, y cuyo proveedor era el
    principal ANTERIOR. Nunca lanza: si algo falla, devuelve `[]` y el modal no
    aparece — cambiar el ★ en el catálogo no puede tumbar el guardado.
    """
    if not anterior_id:
        return []
    try:
        lineas = (
            _lineas_vivas(servicio)
            .filter(proveedor_id=anterior_id)
            .select_related("proyecto", "proyecto__cliente", "servicio", "variacion")
            .order_by("proyecto__codigo", "orden", "pk")
        )
        return [linea for linea in lineas if not _tiene_cotizacion_pagada(linea.proyecto)]
    except Exception:  # noqa: BLE001 — el modal es un extra; el producto ya se guardó
        return []


def propagar_proveedor(servicio, anterior_id, nuevo_id, linea_ids, actor=None) -> int:
    """Pone el proveedor NUEVO en las líneas que el usuario dejó marcadas.

    Cada id se vuelve a validar contra la misma regla del modal: lo que llega del
    navegador no se cree (una línea que entretanto se pagó, o de otro producto,
    se salta en silencio). Devuelve cuántas líneas cambiaron. Nunca lanza.
    """
    try:
        return _propagar_proveedor(servicio, anterior_id, nuevo_id, linea_ids, actor)
    except Exception:  # noqa: BLE001
        return 0


def _propagar_proveedor(servicio, anterior_id, nuevo_id, linea_ids, actor) -> int:
    from apps.los_proyectos.models import ProyectoProducto

    from .models import Proveedor

    if not anterior_id or not nuevo_id or int(anterior_id) == int(nuevo_id):
        return 0
    if not Proveedor.objects.filter(pk=nuevo_id, activo=True).exists():
        return 0
    pedidos = {int(x) for x in linea_ids if str(x).strip().isdigit()}
    if not pedidos:
        return 0
    elegibles = [
        linea for linea in lineas_para_proveedor(servicio, anterior_id)
        if linea.pk in pedidos
    ]
    if not elegibles:
        return 0
    for linea in elegibles:
        linea.proveedor_id = int(nuevo_id)
    # `bulk_update` no dispara el `post_save` que liga el proveedor al catálogo,
    # y no hace falta: el nuevo YA es el principal de este producto.
    ProyectoProducto.objects.bulk_update(elegibles, ["proveedor"])
    emitir(EventoPortavoz(
        tipo="catalogo.proveedor_propagado",
        actor_id=getattr(actor, "pk", None),
        actor_email=getattr(actor, "email", ""),
        payload={
            "servicio_id": servicio.pk,
            "proveedor_anterior": int(anterior_id),
            "proveedor_nuevo": int(nuevo_id),
            "lineas": len(elegibles),
            "proyectos": sorted({linea.proyecto_id for linea in elegibles}),
        },
    ))
    return len(elegibles)
