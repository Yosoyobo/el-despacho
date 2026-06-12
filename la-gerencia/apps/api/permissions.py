"""Permisos DRF para endpoints internos.

El Inventario de Endpoints (Swagger UI) y los endpoints JSON internos solo son
accesibles a super_admin. La auth es SessionAuthentication (cookie
gerencia_session), así que estos permisos cooperan con `lib.permisos`.
"""

from rest_framework.permissions import BasePermission

from lib.permisos import tiene_rol


class SoloSuperAdmin(BasePermission):
    message = "Acceso restringido a super_admin."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        # V6 Bloque 10: reconoce rol primario + roles personalizados.
        return tiene_rol(user, "super_admin")


class AdminOdueno(BasePermission):
    message = "Acceso restringido a administración."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        # V6 Bloque 10: reconoce rol primario + roles personalizados.
        return tiene_rol(user, "super_admin", "dueno")


class SoloSuperAdminOdueno(AdminOdueno):
    """Alias semántico — El Site documenta su acceso con este nombre explícito
    en Swagger. Funcionalmente equivalente a AdminOdueno."""
    message = "Acceso restringido a super_admin y dueño."
