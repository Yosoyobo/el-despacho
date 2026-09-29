"""Middlewares custom de El Despacho.

`RedirigirRolesOperativosMiddleware` — la puerta de La Gerencia, en cada
petición: quien tiene la sesión abierta pero NO tiene `gerencia.acceder`
(super_admin siempre lo tiene: es el failsafe) sale de La Gerencia —se le cierra
la sesión de aquí— y se le manda a El Taller, donde sí pertenece.

Antes decidía por el rol PRIMARIO (sacaba a `contador`/`disenador`). Decisión de
Oscar (2026-09-28): pasa a permiso granular (§4 #20), y a propósito cambia algo
—quien pierde el acceso desde El Directorio sale de inmediato, aunque tenga la
sesión abierta; antes se quedaba hasta que la sesión caducara—. El login
(`auth_gerencia`) y el SSO de Google ya preguntan por el mismo permiso.

Whitelist: paths que NO disparan redirect (auth, assets, healthcheck, etc.).
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponseRedirect

# Paths que el middleware NO toca (auth + assets + healthcheck).
PREFIJOS_WHITELIST = (
    "/sign-in",
    "/sign-out",
    "/auth/",
    "/static/",
    "/sw.js",
    "/manifest.webmanifest",
    "/ping",
    "/oauth/",
)

# Destino al que se manda a quien no tiene acceso a La Gerencia.
# Configurable vía settings.TALLER_URL si se quiere.
TALLER_URL_DEFAULT = "https://taller.learningcenter.mx/"


class RedirigirRolesOperativosMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if self._debe_redirigir(request):
            from django.conf import settings
            from django.contrib.auth import logout

            # «Sale de inmediato»: se cierra la sesión de La Gerencia (la de El
            # Taller es otra cookie y no se toca). Así, si le devuelven el
            # permiso, vuelve a entrar por el login como cualquiera.
            logout(request)
            destino = getattr(settings, "TALLER_URL", TALLER_URL_DEFAULT)
            return HttpResponseRedirect(destino)
        return self.get_response(request)

    @staticmethod
    def _debe_redirigir(request: HttpRequest) -> bool:
        # Path whitelist (auth, assets, healthcheck).
        path = request.path or ""
        for prefijo in PREFIJOS_WHITELIST:
            if path.startswith(prefijo):
                return False
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        from lib.permisos import puede_acceder_gerencia

        return not puede_acceder_gerencia(user)
