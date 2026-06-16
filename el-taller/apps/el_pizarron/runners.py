"""El Runner — asignación de repartidor a tareas de entrega/recolección.

S-LC-Proyecto-V2 (Oscar 2026-06-16). Una tarea tipo `entrega`/`recoger` puede
delegarse a un **runner** (quien lleva o recoge). Se elige manual o
automáticamente ("que el sistema/El Chalán designe al menos cargado").

Auto-asignación (S-Chalan-Barrido): si la tarea tiene una ubicación de DESTINO
(fijada con pin o heredada de la última visita geolocalizada al cliente del
proyecto), elige al runner elegible MÁS CERCANO; si no hay destino o ninguna
posición de runner es conocida, cae a "el menos cargado". Sin geocodificación
de paga: las coordenadas vienen de las visitas/jornadas que ya registra El
Checador (regla "gratis o abortamos"). El Chalán también puede asignar/reasignar
por comando (ejecutor `asignar_runner`).
"""

from __future__ import annotations

import contextlib

from lib.permisos import usuarios_runner

TIPOS_RUNNER = ("entrega", "recoger")


def requiere_runner(tarea) -> bool:
    return tarea.tipo in TIPOS_RUNNER


# ── Ubicación (cero costo: reusa snapshots de El Checador) ────────────────────

def ubicacion_actual_de(usuario):
    """Última posición conocida del usuario: su visita geolocalizada más reciente
    o, en su defecto, la entrada de su jornada de hoy. (lat, lng) o None."""
    from datetime import date

    from apps.checador.models import Jornada, Visita
    v = (
        Visita.objects.filter(usuario=usuario, lat__isnull=False, lng__isnull=False)
        .order_by("-registrado_en").values_list("lat", "lng").first()
    )
    if v:
        return v
    j = (
        Jornada.objects.filter(usuario=usuario, fecha=date.today(),
                               entrada_lat__isnull=False, entrada_lng__isnull=False)
        .values_list("entrada_lat", "entrada_lng").first()
    )
    return j or None


def ubicacion_destino_de_tarea(tarea):
    """Destino de la tarea: el pin explícito, o la última visita geolocalizada al
    cliente del proyecto. (lat, lng) o None."""
    if tarea.destino_lat is not None and tarea.destino_lng is not None:
        return (tarea.destino_lat, tarea.destino_lng)
    cliente_id = getattr(getattr(tarea, "proyecto", None), "cliente_id", None)
    if not cliente_id:
        return None
    from apps.checador.models import Visita
    v = (
        Visita.objects.filter(cliente_id=cliente_id, lat__isnull=False, lng__isnull=False)
        .order_by("-registrado_en").values_list("lat", "lng").first()
    )
    return v or None


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


def elegir_mas_cercano(destino):
    """Runner elegible más cercano a `destino` (lat, lng), desempatando por
    menos cargado. Si NINGÚN candidato tiene posición conocida, devuelve None
    para que el caller caiga a `elegir_menos_cargado`."""
    from apps.checador.models.sede import distancia_m
    if not destino:
        return None
    dest_lat, dest_lng = destino
    candidatos = usuarios_runner()
    con_distancia = []
    for u in candidatos:
        pos = ubicacion_actual_de(u)
        if not pos:
            continue
        d = distancia_m(pos[0], pos[1], dest_lat, dest_lng)
        if d is not None:
            con_distancia.append((d, pendientes_runner(u), u.pk, u))
    if not con_distancia:
        return None
    con_distancia.sort(key=lambda t: (t[0], t[1], t[2]))
    return con_distancia[0][3]


def elegir_runner_auto(tarea):
    """Elige el runner para auto-asignación: por cercanía si hay destino y
    posiciones conocidas; si no, el menos cargado."""
    destino = ubicacion_destino_de_tarea(tarea)
    return elegir_mas_cercano(destino) or elegir_menos_cargado()


def asignar_runner_auto(tarea, *, actor=None):
    """Asigna automáticamente el runner a una tarea de entrega/recolección:
    el MÁS CERCANO al destino si se conoce, si no el MENOS CARGADO. Marca
    `runner_auto`. Devuelve el runner o None. No lanza: si no hay candidatos,
    deja la tarea sin runner."""
    if not requiere_runner(tarea):
        return None
    runner = elegir_runner_auto(tarea)
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
