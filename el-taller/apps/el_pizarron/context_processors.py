"""Badge de Mandados activos para el sidebar — S-Mandados-V2.

Cuenta los mandados abiertos (no terminales) visibles para el usuario, para el
contador del item "Mandados". Defensivo: ante cualquier error devuelve 0.
"""

from __future__ import annotations

import contextlib


def mandados_badge(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"mandados_pendientes_count": 0}
    total = 0
    with contextlib.suppress(Exception):
        from apps.el_pizarron.mandados import mandados_visibles
        total = (
            mandados_visibles(user)
            .exclude(estado__in=("entregado", "cancelado"))
            .count()
        )
    return {"mandados_pendientes_count": total}
