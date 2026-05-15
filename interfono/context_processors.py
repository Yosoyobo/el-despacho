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
