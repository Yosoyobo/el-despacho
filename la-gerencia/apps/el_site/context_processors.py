"""Context processor para el badge ⚠️ del navbar.

Inyecta `site_integraciones_rojas` (int) en todos los templates de La Gerencia.
Se renderiza solo para super_admin/dueno (gate en el template). Falla silente
si las tablas aún no existen (e.g. en tests con DB en memoria).
"""

from __future__ import annotations


def badge_integraciones(request):
    from lib.permisos import tiene_rol

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    # V6 Bloque 10: reconoce rol primario + roles personalizados (roles_extra).
    if not tiene_rol(user, "super_admin", "dueno"):
        return {}
    try:
        from lib.site.almacen import hay_integraciones_rojas
        return {"site_integraciones_rojas": hay_integraciones_rojas()}
    except Exception:
        return {"site_integraciones_rojas": 0}
