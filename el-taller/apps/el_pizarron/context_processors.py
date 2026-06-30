"""Badges del sidebar para Tareas (incluye Mandados, fusionados en V13).

LC 2026-06-30 (decisión Oscar, 2ª pasada): SE CONSERVAN los tres globos, pero
las cuentas ahora SÍ tienen sentido — antes el azul contaba tareas del equipo del
proyecto (no suyas) y el rojo contaba TODOS los mandados visibles (no los suyos),
así que Oscar veía 1/7/3 sin tener nada propio. Definición coherente:

- **Azul** = tareas pendientes **asignadas a mí** (lo que YO tengo que hacer).
- **Gris** = las **demás** tareas pendientes del despacho (conciencia del resto).
- **Rojo** = mandados pendientes **míos** (soy el runner o están asignados a mí).

Quien no tiene nada propio (caso Oscar) ve solo el gris con el total del equipo.
Defensivo: ante cualquier error, 0.
"""

from __future__ import annotations

import contextlib


def mandados_badge(request):
    user = getattr(request, "user", None)
    cero = {
        "tareas_involucrado_count": 0,
        "tareas_otras_count": 0,
        "mandados_pendientes_count": 0,
        # back-compat por si algún template/test viejo aún los lee.
        "tareas_total_count": 0,
        "tareas_general_pendientes_count": 0,
    }
    if not user or not getattr(user, "is_authenticated", False):
        return cero

    mias = 0
    otras = 0
    mandados = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import TIPOS_RUNNER, mandados_visibles
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from django.db.models import Q

        terminales = slugs_terminales_tarea()

        # Tareas (no-runner): azul = asignadas a mí; gris = el resto.
        base = Tarea.objects.exclude(estado__in=terminales).exclude(tipo__in=TIPOS_RUNNER)
        total = base.count()
        mias = base.filter(asignada_a=user).count()
        otras = max(0, total - mias)

        # Rojo = mandados pendientes MÍOS (soy runner o están asignados a mí).
        mandados = (
            mandados_visibles(user)
            .exclude(estado__in=("entregado", "cancelado"))
            .filter(Q(tarea__runner=user) | Q(tarea__asignada_a=user))
            .distinct()
            .count()
        )

    return {
        "tareas_involucrado_count": mias,
        "tareas_otras_count": otras,
        "mandados_pendientes_count": mandados,
        # back-compat:
        "tareas_total_count": mias + otras,
        "tareas_general_pendientes_count": mias,
    }
