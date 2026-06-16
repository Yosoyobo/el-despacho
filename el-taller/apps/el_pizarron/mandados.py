"""El Runner — capa de servicio del Mandado (companion 1:1 de Tarea).

`sincronizar_mandado(tarea)` se llama por señal post_save de Tarea: crea el
Mandado si la tarea es de tipo entrega/recoger y deriva su estado de reparto
del runner + el estado de la tarea (sin pisar la cancelación manual ni el
"en_camino" que marca el runner). Las transiciones manuales (en_camino,
cancelar) viven en services para que la vista/Chalán las invoquen.
"""

from __future__ import annotations

from django.utils import timezone

TIPOS_RUNNER = ("entrega", "recoger")


def _tarea_terminal(tarea) -> bool:
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    return tarea.estado in slugs_terminales_tarea()


def sincronizar_mandado(tarea):
    """Crea/actualiza el Mandado de una tarea de entrega/recoger. Idempotente.

    Estado derivado:
      - cancelado: no se toca (transición manual, gana sobre todo).
      - entregado: la tarea llegó a un estado terminal (completada).
      - en_camino: se preserva (lo marca el runner manualmente).
      - asignado: hay runner y la tarea no está terminal.
      - por_asignar: sin runner.
    """
    if tarea.tipo not in TIPOS_RUNNER:
        return None
    from apps.el_pizarron.models.mandado import Mandado
    mandado, _ = Mandado.objects.get_or_create(tarea=tarea)
    if mandado.estado == "cancelado":
        return mandado

    if _tarea_terminal(tarea):
        target = "entregado"
    elif mandado.estado == "en_camino":
        target = "en_camino"
    elif tarea.runner_id:
        target = "asignado"
    else:
        target = "por_asignar"

    if target != mandado.estado:
        ahora = timezone.now()
        mandado.estado = target
        if target == "asignado" and not mandado.asignado_en:
            mandado.asignado_en = ahora
        elif target == "entregado" and not mandado.entregado_en:
            mandado.entregado_en = ahora
        mandado.save(update_fields=["estado", "asignado_en", "entregado_en", "actualizado_en"])
    return mandado


# ── Transiciones manuales ─────────────────────────────────────────────────────

def marcar_en_camino(mandado):
    if mandado.estado in ("entregado", "cancelado"):
        raise ValueError("El mandado ya está cerrado.")
    mandado.estado = "en_camino"
    if not mandado.en_camino_en:
        mandado.en_camino_en = timezone.now()
    mandado.save(update_fields=["estado", "en_camino_en", "actualizado_en"])
    return mandado


def marcar_entregado(mandado, *, completar_tarea: bool = True):
    """Marca el reparto como entregado. Por defecto también completa la Tarea
    (lleva su estado al primer estado terminal) — así Kanban/Mis tareas quedan
    consistentes y el push de la tarea ya existente aplica."""
    ahora = timezone.now()
    mandado.estado = "entregado"
    if not mandado.entregado_en:
        mandado.entregado_en = ahora
    mandado.save(update_fields=["estado", "entregado_en", "actualizado_en"])
    if completar_tarea:
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        terminales = slugs_terminales_tarea()
        tarea = mandado.tarea
        if tarea.estado not in terminales:
            tarea.estado = next(iter(terminales), "completada")
            tarea.completada_en = ahora
            tarea.save(update_fields=["estado", "completada_en"])
    return mandado


def cancelar(mandado, *, motivo: str = ""):
    mandado.estado = "cancelado"
    mandado.cancelado_en = timezone.now()
    if motivo:
        mandado.notas = (mandado.notas + f"\nCancelado: {motivo}").strip()
    mandado.save(update_fields=["estado", "cancelado_en", "notas", "actualizado_en"])
    return mandado


def fijar_destino(mandado, *, lat, lng, etiqueta: str = ""):
    """Fija el pin de destino en la Tarea subyacente (fuente única)."""
    tarea = mandado.tarea
    tarea.destino_lat = lat
    tarea.destino_lng = lng
    if etiqueta:
        tarea.destino_etiqueta = etiqueta[:200]
    tarea.save(update_fields=["destino_lat", "destino_lng", "destino_etiqueta"])
    return mandado


def mandados_visibles(user):
    """Mandados que el usuario puede ver: si es admin, todos; si no, donde es
    runner o asignado/creador de la tarea. QS con select_related listo."""
    from apps.el_pizarron.models.mandado import Mandado

    from lib.permisos import es_admin
    qs = Mandado.objects.select_related(
        "tarea", "tarea__proyecto", "tarea__proyecto__cliente", "tarea__runner",
    )
    if es_admin(user):
        return qs
    from django.db.models import Q
    return qs.filter(
        Q(tarea__runner=user) | Q(tarea__asignada_a=user) | Q(tarea__creado_por=user)
    ).distinct()
