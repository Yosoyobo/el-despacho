"""Registro de actividad de proyecto (S-Recados-V2 / C5b).

`registrar(...)` deja una fila en ActividadProyecto. Best-effort: cualquier
fallo se traga para no romper la acción que lo dispara (cambiar estado, crear
tarea, comentar, generar egreso, recordatorio de vencimiento).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def registrar(*, proyecto, tipo: str, descripcion: str, actor=None, url: str = "") -> None:
    try:
        from .models import ActividadProyecto
        ActividadProyecto.objects.create(
            proyecto=proyecto, tipo=tipo, descripcion=descripcion[:255],
            actor=actor, url=url[:300],
        )
    except Exception:  # noqa: BLE001
        logger.exception("registrar_actividad falló proyecto=%s tipo=%s",
                         getattr(proyecto, "pk", None), tipo)


def feed_para(usuario, limite: int = 50):
    """Actividad de los proyectos donde el usuario es asignado (cualquier rol).
    Para el tab Actividad de Recados. Admins ven todo."""
    from lib.permisos import es_admin

    from .models import ActividadProyecto
    qs = ActividadProyecto.objects.select_related("proyecto", "actor")
    if not es_admin(usuario):
        qs = qs.filter(proyecto__asignaciones__usuario=usuario).distinct()
    return list(qs[:limite])
