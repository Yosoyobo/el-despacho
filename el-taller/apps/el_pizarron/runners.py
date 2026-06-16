"""El Runner — asignación de repartidor a tareas de entrega/recolección.

S-LC-Proyecto-V2 (Oscar 2026-06-16). Una tarea tipo `entrega`/`recoger` puede
delegarse a un **runner** (quien lleva o recoge). Se elige manual o
automáticamente ("que el sistema/El Chalán designe al menos cargado").

V1: la auto-asignación elige al runner elegible con MENOS entregas/recolecciones
abiertas. Geo ("el más cercano") queda como deuda diseñada — requiere
geocodificar destinos. El Chalán también puede asignar/reasignar por comando
(ejecutor `asignar_runner`).
"""

from __future__ import annotations

import contextlib

from lib.permisos import usuarios_runner

TIPOS_RUNNER = ("entrega", "recoger")


def requiere_runner(tarea) -> bool:
    return tarea.tipo in TIPOS_RUNNER


def pendientes_runner(usuario) -> int:
    """Entregas/recolecciones abiertas (no terminales) asignadas a `usuario`."""
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.models.tarea import Tarea
    return (
        Tarea.objects.filter(runner=usuario, tipo__in=TIPOS_RUNNER)
        .exclude(estado__in=slugs_terminales_tarea())
        .count()
    )


def elegir_menos_cargado():
    """Runner elegible con menos pendientes abiertos (None si no hay candidatos)."""
    candidatos = usuarios_runner()
    if not candidatos:
        return None
    return min(candidatos, key=lambda u: (pendientes_runner(u), u.pk))


def asignar_runner_auto(tarea, *, actor=None):
    """Asigna automáticamente el runner menos cargado a una tarea de
    entrega/recolección. Marca `runner_auto`. Devuelve el runner o None.
    No lanza: si no hay candidatos, deja la tarea sin runner."""
    if not requiere_runner(tarea):
        return None
    runner = elegir_menos_cargado()
    if runner is None:
        return None
    from django.utils import timezone
    tarea.runner = runner
    tarea.runner_auto = True
    tarea.requiere_runner = True
    tarea.runner_asignado_en = timezone.now()
    tarea.save(update_fields=["runner", "runner_auto", "requiere_runner", "runner_asignado_en"])
    _notificar_runner(tarea, actor)
    return runner


def asignar_runner(tarea, runner, *, actor=None):
    """Asigna un runner explícito (manual). Marca `runner_auto=False`."""
    from django.utils import timezone
    tarea.runner = runner
    tarea.runner_auto = False
    tarea.requiere_runner = True
    tarea.runner_asignado_en = timezone.now()
    tarea.save(update_fields=["runner", "runner_auto", "requiere_runner", "runner_asignado_en"])
    _notificar_runner(tarea, actor)
    return runner


def aplicar_desde_form(tarea, cleaned, *, actor=None):
    """Aplica la elección de runner del form a una tarea recién guardada.
    Solo hace algo si el tipo es entrega/recoger."""
    if not requiere_runner(tarea):
        return
    elegido = cleaned.get("runner")
    if elegido:
        asignar_runner(tarea, elegido, actor=actor)
    elif cleaned.get("runner_auto"):
        asignar_runner_auto(tarea, actor=actor)
    elif not tarea.requiere_runner:
        tarea.requiere_runner = True
        tarea.save(update_fields=["requiere_runner"])


def _notificar_runner(tarea, actor):
    """Push al runner — best-effort, nunca tumba la asignación."""
    if not tarea.runner_id or tarea.runner_id == getattr(actor, "id", None):
        return
    with contextlib.suppress(Exception):
        from lib.interfono import enviar_a_usuario
        verbo = "Recoger" if tarea.tipo == "recoger" else "Entregar"
        enviar_a_usuario(
            tarea.runner,
            titulo=f"{verbo}: {tarea.titulo[:60]}",
            cuerpo=f"{tarea.proyecto.codigo} · {tarea.proyecto.cliente.razon_social}",
            url=f"/proyectos/{tarea.proyecto_id}/",
            categoria="tareas",
        )
