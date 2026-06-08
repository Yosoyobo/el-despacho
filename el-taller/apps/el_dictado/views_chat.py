"""Views del Chat conversacional del Taller (El Chalán) — S-Chalan-Chat-V1.

Sección `/chalan/` estilo TailAdmin AI: lista de conversaciones + chat activo +
"Nuevo chat". El textarea del Dashboard crea un chat nuevo y redirige aquí.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import ConversacionChat, Dictado
from .services import aplicar
from .services_chat import chat_acepta_imagenes, conversar, crear_conversacion


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _imagenes_de_request(request) -> list | None:
    """Lee una imagen adjunta del request (campo `imagen`), la valida y la
    devuelve como lista de dicts `{base64, media_type}` para `conversar`.
    Solo imágenes (el chat con visión no lee PDFs). Best-effort: si algo
    falla, devuelve None y el chat sigue como texto."""
    archivo = request.FILES.get("imagen")
    if not archivo:
        return None
    from lib import adjuntos
    if adjuntos.validar(archivo):
        return None
    media = (getattr(archivo, "content_type", "") or "").lower()
    if not media.startswith("image/"):
        return None
    import base64
    contenido = archivo.read()
    return [{"base64": base64.b64encode(contenido).decode("ascii"), "media_type": media}]


def _conversaciones_de(usuario):
    return ConversacionChat.objects.filter(usuario=usuario, archivada=False).order_by("-actualizado_en")[:50]


def _render_shell(request, conversacion):
    mensajes = list(conversacion.mensajes.order_by("orden")) if conversacion else []
    ultimo_id = mensajes[-1].pk if mensajes else 0
    return render(request, "el_dictado/chat.html", {
        "conversaciones": _conversaciones_de(request.user),
        "conversacion": conversacion,
        "mensajes": mensajes,
        "ultimo_id": ultimo_id,
        "chat_vision_ok": chat_acepta_imagenes(request.user),
    })


@login_required
def chat(request):
    """GET /chalan/ — abre la conversación más reciente o el estado vacío."""
    conversacion = _conversaciones_de(request.user).first()
    return _render_shell(request, conversacion)


@login_required
def conversacion(request, pk: int):
    """GET /chalan/c/<pk>/ — abre una conversación específica."""
    conv = get_object_or_404(ConversacionChat, pk=pk, usuario=request.user)
    return _render_shell(request, conv)


@login_required
@require_http_methods(["POST"])
def nuevo(request):
    """POST /chalan/nuevo — crea un chat nuevo (con mensaje inicial opcional del
    Dashboard) y redirige a la sección de chat con ese chat abierto."""
    mensaje = (request.POST.get("mensaje") or request.POST.get("texto") or "").strip()
    conv = crear_conversacion(usuario=request.user, mensaje_inicial=mensaje or None)
    if mensaje:
        conversar(mensaje=mensaje, usuario=request.user, conversacion=conv)
    return redirect("chalan-conversacion", pk=conv.pk)


@login_required
@require_http_methods(["POST"])
def enviar(request, pk: int):
    """POST /chalan/c/<pk>/enviar — corre el loop y devuelve los turnos nuevos."""
    conv = get_object_or_404(ConversacionChat, pk=pk, usuario=request.user)
    mensaje = (request.POST.get("mensaje") or "").strip()
    imagenes = _imagenes_de_request(request)
    if not mensaje and not imagenes:
        if _es_htmx(request):
            return render(request, "el_dictado/_chat_mensajes.html", {"mensajes": []})
        return redirect("chalan-conversacion", pk=pk)
    resultado = conversar(mensaje=mensaje, usuario=request.user, conversacion=conv, imagenes=imagenes)
    if _es_htmx(request):
        return render(request, "el_dictado/_chat_mensajes.html", {"mensajes": resultado["mensajes"]})
    return redirect("chalan-conversacion", pk=pk)


@login_required
@require_http_methods(["POST"])
def aplicar_accion(request, pk: int):
    """POST /chalan/<dpk>/aplicar — confirma y aplica las acciones del Dictado
    (reusa `services.aplicar`). Agrega un mensaje de resultado a la conversación."""
    from .models import MensajeChat
    from .services_chat import _crear_mensaje

    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user, origen="taller_chat")
    msg = MensajeChat.objects.filter(dictado=dictado).select_related("conversacion").first()
    conv = msg.conversacion if msg else None

    if dictado.estado not in ("esperando_confirmacion", "confirmado_parcial"):
        messages.warning(request, "Estas acciones ya no se pueden aplicar.")
        return redirect("chalan-conversacion", pk=conv.pk) if conv else redirect("chalan-chat")

    marcadas = {int(k.split("_")[1]) for k in request.POST if k.startswith("accion_")}
    for accion in dictado.acciones.all():
        nueva = accion.pk in marcadas
        if accion.confirmada != nueva:
            accion.confirmada = nueva
            accion.save(update_fields=["confirmada"])

    resultado = aplicar(dictado=dictado, usuario=request.user)
    if conv is not None:
        _crear_mensaje(
            conv, rol="bot", chalan=dictado.chalan,
            cuerpo=f"Listo: {resultado['aplicadas']} acción(es) aplicada(s), {resultado['fallidas']} con error.",
        )
        conv.save(update_fields=["actualizado_en"])
        return redirect("chalan-conversacion", pk=conv.pk)
    return redirect("chalan-chat")


@login_required
@require_http_methods(["POST"])
def cancelar_accion(request, pk: int):
    """POST /chalan/<dpk>/cancelar — descarta la propuesta de acción."""
    from .models import MensajeChat

    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user, origen="taller_chat")
    if dictado.estado in ("esperando_confirmacion", "confirmado_parcial"):
        dictado.estado = "cancelado"
        dictado.save(update_fields=["estado"])
    msg = MensajeChat.objects.filter(dictado=dictado).select_related("conversacion").first()
    if msg:
        return redirect("chalan-conversacion", pk=msg.conversacion_id)
    return redirect("chalan-chat")


@login_required
def lista(request):
    """GET /chalan/partial/lista — refresca la sidebar de conversaciones."""
    return render(request, "el_dictado/_chat_lista.html", {
        "conversaciones": _conversaciones_de(request.user),
        "conversacion": None,
    })
