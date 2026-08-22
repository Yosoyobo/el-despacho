"""Vista compartida de respaldo para los derivados de El Almacén.

En producción esta ruta **casi nunca se ejecuta**: El Portero (Caddy) sirve
`/medios/*` directo del disco. Django sólo entra cuando el derivado no está —
un `pub/` borrado a mano, un restore que sólo trajo los originales, o el propio
`docker compose` de HAL sin Caddy delante. Regenera el archivo desde el original
y lo sirve; a partir de ahí lo vuelve a servir Caddy.

Se monta en el `urls.py` de cada Django project:

    from lib.medios_views import urlpatterns_medios
    urlpatterns += urlpatterns_medios

**Pública a propósito**, igual que la ruta de Caddy: la URL es la capacidad (una
huella de 64 hex que no se adivina ni se lista, con `X-Robots-Tag: noindex`). Si
exigiera sesión, el respaldo redirigiría al login y la imagen saldría rota — y
sólo alcanza derivados hechos por nosotros, nunca un archivo subido por alguien:
los originales viven en `orig/`, que ni Caddy ni esta vista tocan.
"""

from __future__ import annotations

from django.http import FileResponse, HttpResponse
from django.urls import re_path
from django.views.decorators.http import require_safe

from lib import almacen

# Mismo año que la ruta de Caddy: la ruta lleva la huella del contenido, así que
# el archivo de una URL nunca cambia y el navegador no necesita revalidar.
CACHE = "public, max-age=31536000, immutable"

_MIME = {"jpg": "image/jpeg", "png": "image/png"}


@require_safe
def medio_derivado(request, a: str, b: str, huella: str, variante: str, ext: str):
    """`GET /medios/<a>/<b>/<huella>/<variante>.<ext>`"""
    # La huella se reparte en subcarpetas por sus dos primeros pares: si los
    # tramos de la URL no coinciden, la ruta está inventada.
    if not huella.startswith(a + b):
        return HttpResponse(status=404)

    ruta = almacen.dir_pub_por_huella(huella) / f"{variante}.{ext}"
    if not ruta.is_file():
        regenerado = almacen.derivar_por_huella(huella, variante, ext)
        if regenerado is None:
            return HttpResponse(status=404)
        ruta = regenerado

    resp = FileResponse(ruta.open("rb"), content_type=_MIME.get(ext, "image/jpeg"))
    resp["Cache-Control"] = CACHE
    resp["X-Content-Type-Options"] = "nosniff"
    resp["X-Robots-Tag"] = "noindex"
    return resp


# El patrón valida por sí solo: dos pares hex, 64 hex de huella, una variante
# conocida y sólo las extensiones que generamos. Nada más entra, así que no hay
# forma de pedir una ruta de más arriba (`..`) ni un archivo ajeno.
_VARIANTES = "|".join(almacen.VARIANTES)

urlpatterns_medios = [
    re_path(
        rf"^medios/(?P<a>[0-9a-f]{{2}})/(?P<b>[0-9a-f]{{2}})/"
        rf"(?P<huella>[0-9a-f]{{64}})/(?P<variante>{_VARIANTES})\.(?P<ext>jpg|png)$",
        medio_derivado,
        name="medio-derivado",
    ),
]

__all__ = ["medio_derivado", "urlpatterns_medios"]
