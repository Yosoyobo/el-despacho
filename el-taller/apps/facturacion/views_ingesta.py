"""La puerta por la que entran los CFDI que manda n8n.

Del otro lado hay un robot, no una persona: n8n vigila el buzón de
`facturas@`, saca el XML adjunto y lo empuja aquí. Por eso la puerta se ve
distinta a todo lo demás del repo — sin sesión, sin formulario, sin CSRF — y
por eso la credencial es lo único que la sostiene.

**Se cierra, no se abre.** Sin token configurado no pasa nadie. Un extremo que
al faltarle la credencial deja entrar a todos es peor que uno sin credencial,
porque da la impresión de estar protegido. Es el mismo criterio de El Celador,
del que se copia el mecanismo entero.

El token se compara con `compare_digest` y no con `==`: el tiempo de una
comparación normal delata el contenido letra por letra.
"""

from __future__ import annotations

import hmac
import json
import logging
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

SLOT_BOVEDA = "cfdi_ingesta_token"
ENV_TOKEN = "CFDI_INGESTA_TOKEN"
CABECERA = "x-cfdi-token"

#: Un CFDI son unos pocos KB. El tope de aquí es la primera línea: rechazar por
#: tamaño cuesta nada y evita hasta leer lo que venga.
MAX_CUERPO = 1024 * 1024


def _tokens() -> list[str]:
    """Los aceptados: el de Los Ajustes y el del entorno. Vacío = nadie pasa."""
    salida = []
    try:
        from ajustes.models.credencial import Credencial

        v = (Credencial.obtener(SLOT_BOVEDA) or "").strip()
        if v:
            salida.append(v)
    except Exception:  # noqa: BLE001 — sin base, queda el del entorno
        pass
    v = (os.environ.get(ENV_TOKEN) or "").strip()
    if v:
        salida.append(v)
    return salida


def _autorizado(request) -> bool:
    dado = (request.headers.get(CABECERA) or "").strip()
    if not dado:
        return False
    aceptados = _tokens()
    if not aceptados:
        return False
    # Se recorren todos sin cortar al primer acierto, para no filtrar por
    # tiempo cuál de los dos orígenes casó.
    ok = False
    for bueno in aceptados:
        if hmac.compare_digest(dado.encode(), bueno.encode()):
            ok = True
    return ok


@csrf_exempt
@require_POST
def cfdi_entrante(request):
    """Recibe un CFDI. Responde siempre JSON, nunca una traza.

    Del otro lado hay un robot: una excepción de Django sin capturar le
    llegaría como una página de error de la que no puede sacar nada, y el
    correo se perdería sin que nadie se entere.
    """
    if not _autorizado(request):
        # 404 y no 403: a quien no trae credencial no se le confirma siquiera
        # que esta puerta existe.
        return JsonResponse({"ok": False, "error": "no encontrado"}, status=404)

    contenido = b""
    nombre = "cfdi.xml"
    try:
        subido = request.FILES.get("archivo") or request.FILES.get("file")
        if subido is not None:
            if subido.size > MAX_CUERPO:
                return JsonResponse({"ok": False, "error": "el archivo es demasiado grande"},
                                    status=413)
            contenido = subido.read()
            nombre = getattr(subido, "name", nombre)
        else:
            contenido = request.body or b""
            if len(contenido) > MAX_CUERPO:
                return JsonResponse({"ok": False, "error": "el cuerpo es demasiado grande"},
                                    status=413)
            # n8n puede mandarlo envuelto en JSON, en base64.
            if contenido[:1] == b"{":
                try:
                    datos = json.loads(contenido)
                    import base64

                    crudo = datos.get("xml") or datos.get("contenido") or ""
                    nombre = datos.get("nombre") or nombre
                    contenido = (base64.b64decode(crudo) if datos.get("base64")
                                 else str(crudo).encode())
                except Exception:  # noqa: BLE001 — se intenta tal cual
                    pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingesta cfdi: no se pudo leer el cuerpo: %s", exc)
        return JsonResponse({"ok": False, "error": "no se pudo leer el archivo"}, status=400)

    if not contenido:
        return JsonResponse({"ok": False, "error": "no llegó ningún archivo"}, status=400)

    try:
        from . import ingesta_cfdi

        resultado = ingesta_cfdi.recibir(contenido, nombre=nombre)
    except Exception as exc:  # noqa: BLE001 — al robot se le contesta, no se le tira una traza
        logger.exception("ingesta cfdi: falló el procesamiento")
        return JsonResponse({"ok": False, "error": f"error al procesar: {exc}"}, status=500)

    return JsonResponse(resultado, status=200 if resultado.get("ok") else 422)


__all__ = ["CABECERA", "ENV_TOKEN", "SLOT_BOVEDA", "cfdi_entrante"]
