"""Badges del sidebar para Tareas/Mandados.

S-LC-Feedback-V13: el item «Tareas» del sidebar muestra badges —
rojo (mandados pendientes) + tareas generales pendientes.

LC 2026-06-30 (decisión Oscar): los globos de TAREAS distinguen involucramiento.
- **Azul** = tareas pendientes donde el que mira está INVOLUCRADO (asignado o en
  el equipo del proyecto).
- **Gris** = las DEMÁS tareas pendientes (no lo involucran). Así, quien no está
  involucrado solo ve un globo gris con el total; quien sí, ve el azul (sus
  tareas) y el gris (el resto).

Defensivo: ante cualquier error devuelve 0.
"""

from __future__ import annotations

import contextlib


def mandados_badge(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "mandados_pendientes_count": 0,
            "tareas_involucrado_count": 0,
            "tareas_otras_count": 0,
            # back-compat por si algún template viejo aún lo lee.
            "tareas_general_pendientes_count": 0,
        }

    mandados = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import mandados_visibles
        mandados = (
            mandados_visibles(user)
            .exclude(estado__in=("entregado", "cancelado"))
            .count()
        )

    involucrado = 0
    otras = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import TIPOS_RUNNER
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from django.db.models import Q

        base = (
            Tarea.objects.exclude(estado__in=slugs_terminales_tarea())
            .exclude(tipo__in=TIPOS_RUNNER)
        )
        total = base.count()
        involucrado = base.filter(
            Q(asignada_a=user) | Q(proyecto__asignaciones__usuario=user)
        ).distinct().count()
        otras = max(0, total - involucrado)

    return {
        "mandados_pendientes_count": mandados,
        "tareas_involucrado_count": involucrado,
        "tareas_otras_count": otras,
        # back-compat: el azul de antes era "mis tareas / las del despacho".
        "tareas_general_pendientes_count": involucrado,
    }
