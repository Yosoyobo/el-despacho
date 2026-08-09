"""Registra cada intento de acceso. **Nunca lanza.**

La bitácora no puede ser el motivo de que alguien no pueda entrar: si la tabla no
existe todavía, si la base está de malas o si el `request` viene raro, se pierde el
registro y el login sigue su camino.

Se llama desde los tres caminos de entrada:

- `apps/auth_taller/views.py` (El Taller, email y contraseña)
- `apps/auth_gerencia/views.py` (La Gerencia, email y contraseña)
- `auth_google/views.py` (SSO de Google, las tres apps)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def ip_de(request) -> str:
    """La dirección del cliente. Detrás de El Portero (Caddy) `REMOTE_ADDR` es el
    proxy, así que se prefiere el primer salto de `X-Forwarded-For`, que es quien
    de verdad pegó."""
    try:
        adelantada = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        return (adelantada or request.META.get("REMOTE_ADDR") or "")[:64]
    except Exception:  # noqa: BLE001
        return ""


def registrar(
    request,
    *,
    app: str,
    exito: bool,
    motivo: str,
    email: str = "",
    usuario=None,
    via: str = "password",
) -> None:
    try:
        from cuentas.models.intento_acceso import IntentoAcceso

        IntentoAcceso.objects.create(
            app=app,
            via=via,
            email_intentado=(email or "")[:254],
            usuario=usuario if getattr(usuario, "pk", None) else None,
            exito=bool(exito),
            motivo=motivo,
            ip=ip_de(request),
            agente=(request.META.get("HTTP_USER_AGENT") or "")[:300],
        )
    except Exception:  # noqa: BLE001 — auditar nunca puede tumbar un login
        logger.warning("auditoria_acceso: no se pudo registrar el intento", exc_info=True)


__all__ = ["ip_de", "registrar"]
