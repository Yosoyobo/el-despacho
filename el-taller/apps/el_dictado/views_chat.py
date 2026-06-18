"""Views del Chat conversacional del Taller (El Chalán) — S-Chalan-Chat-V1.

Sección `/chalan/` estilo TailAdmin AI: lista de conversaciones + chat activo +
"Nuevo chat". El textarea del Dashboard crea un chat nuevo y redirige aquí.
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods

from lib.permisos import puede

from .models import ConversacionChat, Dictado
from .services import aplicar
from .services_chat import chat_acepta_imagenes, conversar, crear_conversacion


def _requiere_chalan(view):
    """Gate del chat de El Chalán por (chalan, usar). Defensa en profundidad:
    el sidebar y el Dashboard ya lo ocultan, pero las URLs también lo exigen."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not puede(request.user, "chalan", "usar"):
            return HttpResponseForbidden("No tienes permiso para usar El Chalán.")
        return view(request, *args, **kwargs)
    return wrapper


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
    import contextlib
    contenido = archivo.read()
    # Rebobina para que el mismo UploadedFile pueda re-leerse al persistirlo
    # en Drive (lib.adjuntos.subir hace otro .read()).
    with contextlib.suppress(Exception):
        archivo.seek(0)
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
@_requiere_chalan
def chat(request):
    """GET /chalan/ — abre la conversación más reciente o el estado vacío."""
    conversacion = _conversaciones_de(request.user).first()
    return _render_shell(request, conversacion)


@login_required
@_requiere_chalan
def conversacion(request, pk: int):
    """GET /chalan/c/<pk>/ — abre una conversación específica."""
    conv = get_object_or_404(ConversacionChat, pk=pk, usuario=request.user)
    return _render_shell(request, conv)


@login_required
@_requiere_chalan
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
@_requiere_chalan
@require_http_methods(["POST"])
def enviar(request, pk: int):
    """POST /chalan/c/<pk>/enviar — corre el loop y devuelve los turnos nuevos."""
    conv = get_object_or_404(ConversacionChat, pk=pk, usuario=request.user)
    mensaje = (request.POST.get("mensaje") or "").strip()
    imagenes = _imagenes_de_request(request)
    archivo = request.FILES.get("imagen") if imagenes else None
    if not mensaje and not imagenes:
        if _es_htmx(request):
            return render(request, "el_dictado/_chat_mensajes.html", {"mensajes": []})
        return redirect("chalan-conversacion", pk=pk)
    resultado = conversar(
        mensaje=mensaje, usuario=request.user, conversacion=conv,
        imagenes=imagenes, archivo_adjunto=archivo,
    )
    if _es_htmx(request):
        return render(request, "el_dictado/_chat_mensajes.html", {"mensajes": resultado["mensajes"]})
    return redirect("chalan-conversacion", pk=pk)


@login_required
@_requiere_chalan
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
        if resultado["fallidas"]:
            # Surface el error CONCRETO de cada acción fallida (no un "con error"
            # mudo). Así el usuario sabe qué faltó y puede reformular.
            detalles = "\n".join(
                f"• {a.descripcion or a.tipo}: {a.error_al_aplicar}"
                for a in dictado.acciones.filter(confirmada=True, aplicada=False)
                if (a.error_al_aplicar or "").strip()
            )
            cuerpo = f"Apliqué {resultado['aplicadas']} y {resultado['fallidas']} no se pudieron:"
            if detalles:
                cuerpo += "\n" + detalles
        else:
            cuerpo = f"Listo: {resultado['aplicadas']} acción(es) aplicada(s)."
        _crear_mensaje(conv, rol="bot", chalan=dictado.chalan, cuerpo=cuerpo)
        conv.save(update_fields=["actualizado_en"])
        return redirect("chalan-conversacion", pk=conv.pk)
    return redirect("chalan-chat")


@login_required
@_requiere_chalan
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
@_requiere_chalan
@require_http_methods(["GET"])
def adjunto_descargar(request, pk: int):
    """GET /chalan/adjunto/<pk> — sirve un adjunto del chat desde Drive (proxy
    autenticado). Solo el dueño de la conversación puede bajarlo."""
    from urllib.parse import quote

    from .models import MensajeChatAdjunto

    adj = get_object_or_404(
        MensajeChatAdjunto.objects.select_related("mensaje__conversacion"), pk=pk
    )
    if adj.mensaje.conversacion.usuario_id != request.user.pk:
        raise Http404("Adjunto no encontrado.")

    from lib.google_drive import drive
    try:
        contenido, mime, nombre = drive.descargar(adj.drive_file_id)
    except Exception:  # noqa: BLE001
        raise Http404("No se pudo obtener el archivo de Drive.") from None

    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    disposicion = "inline" if (mime or "").startswith(("image/", "application/pdf")) else "attachment"
    resp["Content-Disposition"] = f"{disposicion}; filename*=UTF-8''{quote(nombre)}"
    return resp


@login_required
@require_http_methods(["POST"])
def propuesta_descartar(request, pk: int):
    """POST /chalan/propuesta/<pk>/descartar — el usuario descarta una sugerencia
    proactiva de El Chalán. Solo login (la propuesta ya es suya); no exige el
    permiso del chat para que siempre se pueda quitar del Dashboard."""
    from django.utils import timezone

    from .models import PropuestaChalan
    prop = get_object_or_404(PropuestaChalan, pk=pk, usuario=request.user)
    if prop.estado == "pendiente":
        prop.estado = "descartada"
        prop.resuelta_en = timezone.now()
        prop.save(update_fields=["estado", "resuelta_en"])
    return redirect(request.META.get("HTTP_REFERER") or "taller-home")


@login_required
def analisis_modal(request, pk: int):
    """GET /chalan/analisis/<pk>/ — modal HTMX (Wave 5) con el análisis del
    negocio que El Chalán dejó como notificación. Solo el dueño lo ve; al abrirlo
    se marca como visto."""
    from django.utils import timezone

    from .models import PropuestaChalan
    prop = get_object_or_404(PropuestaChalan, pk=pk, usuario=request.user)
    if prop.estado == "pendiente":
        prop.estado = "vista"
        prop.resuelta_en = timezone.now()
        prop.save(update_fields=["estado", "resuelta_en"])

    cuerpo_html = f"<p class='whitespace-pre-line'>{escape(prop.cuerpo)}</p>"
    try:
        import markdown as _md
        cuerpo_html = _md.markdown(prop.cuerpo or "", extensions=["nl2br"])
    except Exception:  # noqa: BLE001 — si falla markdown, queda el texto escapado
        pass
    sello = prop.creada_en.strftime("%Y-%m-%d %H:%M") if prop.creada_en else ""
    cuerpo = (
        f"<div class='space-y-2 leading-relaxed [&_ul]:list-disc [&_ul]:pl-5 "
        f"[&_li]:mt-1'>{cuerpo_html}</div>"
        f"<p class='mt-4 text-xs text-gray-400'>Análisis de El Chalán · {sello}</p>"
    )
    return render(request, "_componentes_tailadmin/_modal_htmx.html", {
        "titulo": prop.titulo,
        "cuerpo": mark_safe(cuerpo),  # noqa: S308 — markdown + escape fallback
        "tamano": "lg",
    })


@login_required
@_requiere_chalan
def lista(request):
    """GET /chalan/partial/lista — refresca la sidebar de conversaciones."""
    return render(request, "el_dictado/_chat_lista.html", {
        "conversaciones": _conversaciones_de(request.user),
        "conversacion": None,
    })
