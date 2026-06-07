"""Middlewares custom de El Despacho.

`RedirigirRolesOperativosMiddleware` — defensa profunda en La Gerencia:
si un usuario autenticado tiene rol `contador` o `disenador`, se le redirige
a https://taller.learningcenter.mx/ (donde sí pertenece). El flujo normal
(`auth_gerencia`) ya rechaza esos roles en `/sign-in`, pero este middleware
cubre el edge case de un cambio de rol mid-sesión o un bookmark stale.

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

# Destino al que se redirige a los roles operativos cuando aterrizan en
# La Gerencia. Configurable vía settings.TALLER_URL si se quiere.
TALLER_URL_DEFAULT = "https://taller.learningcenter.mx/"


class RedirigirRolesOperativosMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if self._debe_redirigir(request):
            from django.conf import settings
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
        return getattr(user, "rol", None) in ("contador", "disenador")
