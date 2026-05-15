"""Permisos DRF para endpoints internos.

El Inventario de Endpoints (Swagger UI) y los endpoints JSON internos solo son
accesibles a super_admin. La auth es SessionAuthentication (cookie
gerencia_session), así que estos permisos cooperan con `lib.permisos`.
"""

from rest_framework.permissions import BasePermission


class SoloSuperAdmin(BasePermission):
    message = "Acceso restringido a super_admin."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "rol", None) == "super_admin"


class AdminOdueno(BasePermission):
    message = "Acceso restringido a administración."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "rol", None) in ("super_admin", "dueno")
