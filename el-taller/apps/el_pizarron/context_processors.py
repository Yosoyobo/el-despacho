"""Badges del sidebar para Tareas/Mandados.

S-LC-Feedback-V13: el item «Tareas» del sidebar muestra DOS badges —
azul (tareas generales pendientes, no-mandado) y rojo (mandados pendientes).
Defensivo: ante cualquier error devuelve 0.
"""

from __future__ import annotations

import contextlib


def mandados_badge(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"mandados_pendientes_count": 0, "tareas_general_pendientes_count": 0}

    mandados = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import mandados_visibles
        mandados = (
            mandados_visibles(user)
            .exclude(estado__in=("entregado", "cancelado"))
            .count()
        )

    general = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import TIPOS_RUNNER
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from django.db.models import Q

        from lib.permisos import roles_efectivos
        roles = roles_efectivos(user)
        qs = (
            Tarea.objects.exclude(estado__in=slugs_terminales_tarea())
            .exclude(tipo__in=TIPOS_RUNNER)
        )
        if not (roles & {"super_admin", "dueno", "contador"}):
            qs = qs.filter(
                Q(asignada_a=user) | Q(proyecto__asignaciones__usuario=user)
            ).distinct()
        general = qs.count()

    return {
        "mandados_pendientes_count": mandados,
        "tareas_general_pendientes_count": general,
    }
