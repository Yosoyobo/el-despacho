"""La puerta por la que entra el papeleo que manda el buzón.

Del otro lado hay un robot —n8n vigilando un correo—, no una persona. Por eso
esta puerta se ve distinta a todo lo demás del repo: sin sesión, sin
formulario, sin CSRF. El mecanismo es el de `facturacion/views_ingesta.py`, del
que se copia entero, con su misma regla:

**se cierra, no se abre.** Sin token configurado no pasa nadie. Un extremo que
al faltarle la credencial deja entrar a todos es peor que uno sin credencial,
porque da la impresión de estar protegido.

El token se compara con `compare_digest` y no con `==`: el tiempo de una
comparación normal delata el contenido letra por letra.

**Qué NO entra por aquí:** los CFDI. Tienen su propia puerta, que los liga a su
factura y les saca el UUID. Si un XML de CFDI llegara aquí acabaría archivado
como papeleo suelto, sin ligar a nada — así que se rechaza con la dirección
correcta en el mensaje.
"""

from __future__ import annotations

import hmac
import logging
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

SLOT_BOVEDA = "papeleo_entrada_token"
ENV_TOKEN = "PAPELEO_ENTRADA_TOKEN"
CABECERA = "x-papeleo-token"

#: Un contrato escaneado son unos megas. El tope es la primera línea: rechazar
#: por tamaño cuesta nada y evita hasta leer lo que venga.
MAX_ARCHIVO = 25 * 1024 * 1024


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
def papeleo_entrante(request):
    """Recibe un archivo y lo deja en el archivo del papeleo.

    Responde siempre JSON, nunca una traza: del otro lado hay un robot, y una
    página de error de Django no le dice nada — el documento se perdería sin
    que nadie se entere.
    """
    if not _autorizado(request):
        # 404 y no 403: a quien no trae credencial no se le confirma siquiera
        # que esta puerta existe.
        return JsonResponse({"ok": False, "error": "no encontrado"}, status=404)

    subido = (request.FILES.get("archivo") or request.FILES.get("file")
              or request.FILES.get("document"))
    if subido is None:
        return JsonResponse({"ok": False, "error": "no llegó ningún archivo"},
                            status=400)
    if subido.size > MAX_ARCHIVO:
        return JsonResponse({"ok": False, "error": "el archivo es demasiado grande"},
                            status=413)

    nombre = getattr(subido, "name", "documento") or "documento"
    if nombre.lower().endswith(".xml"):
        return JsonResponse({
            "ok": False,
            "error": ("los CFDI entran por /facturacion/cfdi-entrante, que los liga "
                      "a su factura; aquí quedarían como papeleo suelto"),
        }, status=422)

    try:
        contenido = subido.read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("papeleo: no se pudo leer el archivo: %s", exc)
        return JsonResponse({"ok": False, "error": "no se pudo leer el archivo"},
                            status=400)

    from lib import paperless

    if not paperless.esta_configurado():
        return JsonResponse({
            "ok": False,
            "error": ("el archivo de papeleo no está conectado: falta la llave de "
                      "Paperless en Gerencia → Papeleo"),
        }, status=503)

    titulo = (request.POST.get("titulo") or "").strip()
    etiquetas: list[int] = []
    try:
        from ajustes.models import ConfiguracionPapeleo

        marca = (ConfiguracionPapeleo.obtener().etiqueta_entrada or "").strip()
        if marca:
            eid = paperless.id_de_etiqueta(marca)
            if eid:
                etiquetas.append(eid)
    except Exception as exc:  # noqa: BLE001 — sin etiqueta se archiva igual
        logger.warning("papeleo: no se pudo resolver la etiqueta: %s", exc)

    tarea = paperless.subir(contenido, nombre, titulo=titulo, etiquetas_ids=etiquetas)
    if not tarea:
        return JsonResponse({"ok": False, "error": "el archivo no aceptó el documento"},
                            status=502)

    # El documento AÚN NO EXISTE: Paperless devolvió el id de la tarea y su OCR
    # corre después. Por eso aquí no se puede ligar todavía —no hay texto que
    # leer ni id que guardar— y la respuesta lo dice en lugar de prometerlo.
    return JsonResponse({
        "ok": True,
        "tarea": tarea,
        "nota": ("recibido; el archivo lo va a leer en unos minutos y hasta "
                 "entonces no se puede buscar por su texto"),
    }, status=202)


__all__ = ["CABECERA", "ENV_TOKEN", "MAX_ARCHIVO", "SLOT_BOVEDA", "papeleo_entrante"]
