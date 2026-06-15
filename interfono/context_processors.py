"""Context processor: inyecta la public key VAPID en todos los templates.

Si las credenciales no están configuradas o La Bóveda no descifra, retorna
`None` y los templates muestran un mensaje "Notificaciones no configuradas".
"""

from __future__ import annotations


def vapid_public_key(request) -> dict:
    try:
        from lib.interfono import InterfonoConfig
        return {"vapid_public_key": InterfonoConfig.vapid_public_key()}
    except Exception:
        return {"vapid_public_key": None}


def notificaciones_no_leidas(request) -> dict:
    """S-LC-Feedback-V10 — contador ROJO de notificaciones sin ver en el sidebar.

    "Sin ver" = `InterfonoEntrega.visto_en is NULL`. Abrir
    `/perfil/notificaciones/` las marca vistas y el badge se vacía. Defensivo:
    cualquier fallo ⇒ 0 (nunca tumba el layout).
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"notificaciones_no_leidas": 0}
    try:
        from interfono.models import InterfonoEntrega
        n = InterfonoEntrega.objects.filter(usuario=user, visto_en__isnull=True).count()
    except Exception:
        return {"notificaciones_no_leidas": 0}
    return {"notificaciones_no_leidas": n}
