"""Context processor solo-Taller: counter de mensajes de chat no leídos.

Tras sprint S-Recados-Chat el counter cuenta `Mensaje` no leído por el
usuario (vía `MensajeLectura.ultimo_mensaje_id`). Si el usuario no
tiene permiso `recados.ver`, devuelve 0 sin tocar la base.
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
        from apps.recados.services_chat import total_no_leidos
        n = total_no_leidos(user)
    except Exception:
        return {"recados_no_leidos_count": 0}
    return {"recados_no_leidos_count": n}
