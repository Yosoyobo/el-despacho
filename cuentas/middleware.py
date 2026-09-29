"""Middleware compartido de cuentas.

`PresenciaMiddleware` anota la última actividad del usuario al terminar cada
petición (sprint de pendientes 2026-09-28). Todo el criterio vive en
`lib.presencia.registrar`: qué cuenta como actividad (el sondeo automático NO),
cuándo toca escribir (a lo más una vez por minuto en la misma pantalla) y qué
pantalla se anota (la que la persona tiene enfrente, no el fragmento HTMX).

Va en El Taller y en La Gerencia, justo después de la autenticación. Corre en la
vuelta —después de la vista— por dos razones: así sabe si la respuesta fue un
error (un 500 no es estar trabajando) y así lee `request.impersonador`, que
pone el middleware de impersonación de El Taller.

`registrar` nunca lanza. Una presencia que no se pudo anotar se pierde; una
pantalla que se cae porque no se pudo anotar la presencia sería absurdo.
"""

from __future__ import annotations

from collections.abc import Callable


class PresenciaMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        from lib import presencia

        presencia.registrar(request, response)
        return response
