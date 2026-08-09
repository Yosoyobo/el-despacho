"""Vista compartida del extremo `/salud` — la lee el monitor del taller.

Se monta en el `urls.py` de cada Django project:

    from lib.salud_views import salud
    urlpatterns += [path("salud", salud, name="salud")]

Es pública a propósito (el monitor pregunta desde afuera, sin sesión). Lo que se
contesta de más va detrás de la cabecera `x-celador` — ver `lib/celador.py`.
"""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from lib import celador
from lib import salud as salud_lib

# De qué app viene la respuesta. Útil para el taller: las tres comparten base de
# datos, así que el JSON tiene que decir quién contestó.
_APPS = {
    "el_taller": "taller",
    "la_gerencia": "gerencia",
    "la_recepcion": "recepcion",
    "tests": "pruebas",
}


def _nombre_app() -> str:
    explicito = getattr(settings, "DESPACHO_APP", "")
    if explicito:
        return str(explicito)
    raiz = str(getattr(settings, "ROOT_URLCONF", "") or "").split(".")[0]
    return _APPS.get(raiz, raiz or "desconocida")


@require_safe
def salud(request):
    """`GET /salud` — JSON con `estado` y `modulos[]`.

    - `503` **solo** cuando el estado del conjunto es `falla`; `200` en todo lo demás.
    - `Cache-Control: no-store`: un monitor cacheado miente en verde.
    - `ensure_ascii=False` para que los acentos del detalle se lean como acentos.
    """
    cuerpo, codigo = salud_lib.payload(
        app=_nombre_app(),
        de_la_casa=celador.es_de_la_casa(request),
    )
    resp = JsonResponse(cuerpo, status=codigo, json_dumps_params={"ensure_ascii": False})
    resp["Cache-Control"] = "no-store"
    return resp


__all__ = ["salud"]
