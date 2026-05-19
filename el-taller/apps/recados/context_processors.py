"""Context processor solo-Taller: counter de recados no leídos.

Se evalúa en cada request autenticado. Query barata por el índice
`(usuario, leido_en)` en `recado_destinatario`. Si el usuario no tiene
permiso `recados.ver`, devuelve 0 sin tocar la base.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def recados_no_leidos(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"recados_no_leidos_count": 0}

    try:
        from lib.permisos import puede
        if not puede(user, "recados", "ver"):
            return {"recados_no_leidos_count": 0}
        from apps.recados.models import RecadoDestinatario
        n = RecadoDestinatario.objects.filter(
            usuario=user, leido_en__isnull=True
        ).count()
    except Exception:
        return {"recados_no_leidos_count": 0}
    return {"recados_no_leidos_count": n}
