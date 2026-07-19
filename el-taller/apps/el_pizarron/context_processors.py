"""Badges del sidebar para Tareas (incluye Mandados, fusionados en V13).

LC Fase 1 (2026-07, plan de ajustes): los tres globos de Tareas se redefinen para
que comuniquen el estado del despacho de un vistazo:

- **📋 despacho** = TODAS las tareas del despacho pendientes y en proceso (no
  terminales), de todos. Es el pulso general del taller.
- **💻 mías** = tareas pendientes **asignadas al usuario autenticado** (lo que YO
  tengo que hacer).
- **🛵 mandados** = tareas marcadas como mandado (tipo entrega/recoger) **en
  estados pendiente y en proceso** (no terminales, no canceladas), dentro de lo
  que el usuario puede ver (los runner-only siguen viendo solo los suyos por
  `mandados_visibles`).

**Ninguno cuenta tareas archivadas** (LC Fase 2): archivar esconde la tarea de
la vista, así que tampoco debe inflar los globos del sidebar.

Defensivo: ante cualquier error, 0.
"""

from __future__ import annotations

import contextlib


def mandados_badge(request):
    user = getattr(request, "user", None)
    cero = {
        "tareas_despacho_count": 0,
        "tareas_mias_count": 0,
        "mandados_activos_count": 0,
    }
    if not user or not getattr(user, "is_authenticated", False):
        return cero

    despacho = 0
    mias = 0
    mandados = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import TIPOS_RUNNER, mandados_visibles
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from django.db.models import Q

        terminales = slugs_terminales_tarea()

        # 📋 = todas las tareas (no-runner) pendientes y en proceso del despacho.
        # NO cuenta archivadas (LC Fase 2).
        base = (
            Tarea.objects.filter(archivada=False)
            .exclude(estado__in=terminales)
            .exclude(tipo__in=TIPOS_RUNNER)
        )
        despacho = base.count()
        # 💻 = las que están asignadas a mí.
        mias = base.filter(Q(asignada_a=user) | Q(responsables=user)).distinct().count()

        # 🛵 = tareas de tipo mandado (entrega/recoger) en pendiente/en proceso:
        # su Tarea sigue no-terminal y no está archivada; el mandado no está
        # cancelado. Acotado a lo que el usuario puede ver.
        mandados = (
            mandados_visibles(user)
            .exclude(estado="cancelado")
            .exclude(tarea__estado__in=terminales)
            .filter(tarea__archivada=False)
            .distinct()
            .count()
        )

    return {
        "tareas_despacho_count": despacho,
        "tareas_mias_count": mias,
        "mandados_activos_count": mandados,
    }
