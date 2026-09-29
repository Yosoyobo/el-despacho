"""Permisos DRF para endpoints internos.

El Inventario de Endpoints (Swagger UI) y los endpoints JSON internos solo son
accesibles a super_admin. La auth es SessionAuthentication (cookie
gerencia_session), así que estos permisos cooperan con `lib.permisos`.
"""

from rest_framework.permissions import BasePermission

from lib.permisos import puede_usar_api_site, tiene_rol


class SoloSuperAdmin(BasePermission):
    message = "Acceso restringido a super_admin."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        # V6 Bloque 10: reconoce rol primario + roles personalizados.
        return tiene_rol(user, "super_admin")


class PuedeApiSite(BasePermission):
    """El API JSON de El Site: `site.api` (super_admin siempre).

    S-Deuda-Permisos: antes `AdminOdueno`/`SoloSuperAdminOdueno`, que decidían
    por ROL (super_admin/dueño). Es una acción aparte de `site.ver` porque hoy
    hay quien entra al API sin ver la pantalla, y «como hoy» obliga.
    """
    message = "Sin permiso para el API de El Site."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return puede_usar_api_site(user)
