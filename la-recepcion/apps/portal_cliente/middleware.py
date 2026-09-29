"""La puerta de La Recepción: **cerrada por default**.

Toda petición pasa por aquí. Si la ruta no es pública, hace falta una sesión de
cliente VIVA: acceso activo, cliente activo y la misma `generacion` con la que
se abrió la sesión. Cualquier otra cosa limpia la sesión y manda a `/entrar/`.

Por qué un middleware y no un decorador por vista: en un portal que ve gente de
fuera, olvidar un decorador es abrir una pantalla al mundo (el repo ya lo pagó
dos veces con `@login_required`, CLAUDE.md §8). Aquí la pantalla nueva nace
cerrada y hay que declararla pública a propósito.

Deja `request.acceso` (un `portal.AccesoCliente` o None) y `request.cliente`.
Las vistas filtran TODO por `request.cliente` — nunca por un id que venga en la
URL o el formulario.
"""

from __future__ import annotations

from urllib.parse import quote

from django.shortcuts import redirect

#: Prefijos que se sirven sin sesión. Cada uno tiene su porqué:
RUTAS_PUBLICAS = (
    "/entrar",                  # pedir y canjear el enlace
    "/auth/google/",            # entrar con Google (sólo si el correo tiene acceso)
    "/legal/",                  # privacidad y términos (§4 #8)
    "/ping",                    # healthcheck del compose y de la ventana
    "/salud",                   # el monitor del taller
    "/sistema/aviso-deploy/",   # el banner de mantenimiento (§4 #23)
    "/static/",                 # hojas de estilo e iconos
    "/manifest.webmanifest",    # PWA mínima
    "/favicon.ico",
)


def es_publica(ruta: str) -> bool:
    return any(ruta == p or ruta.startswith(p) for p in RUTAS_PUBLICAS)


class SesionClienteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from portal.servicios import acceso_de_sesion

        request.acceso = None
        request.cliente = None
        sesion = getattr(request, "session", None)
        if sesion is not None and sesion.get("portal_acceso"):
            acceso = acceso_de_sesion(sesion)
            if acceso is None:
                # Revocado, cliente archivado o una sesión de otra generación:
                # se limpia para que la cookie vieja no siga preguntando.
                sesion.flush()
            else:
                request.acceso = acceso
                request.cliente = acceso.cliente
        if request.acceso is None and not es_publica(request.path):
            destino = "/entrar/"
            if request.method == "GET" and request.path not in ("/", ""):
                destino += "?next=" + quote(request.get_full_path(), safe="/")
            return redirect(destino)
        response = self.get_response(request)
        # 2026-09-29: de quién es la petición, para Peticiones en vivo (El Vigía /
        # El Site). gunicorn la escribe en su log y El Portero la quita antes de
        # que salga al navegador (`Caddyfile`, snippet `(sin_quien)`).
        from lib.historial_actividad import CABECERA, cabecera_quien

        quien = cabecera_quien(request)
        if quien:
            response[CABECERA] = quien
        return response
