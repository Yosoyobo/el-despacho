"""Vistas del chat — sprint S-Recados-Chat.

Endpoints (todos bajo `/recados/`):

  GET  /                          → bandeja (lista de conversaciones)
  GET  /partials/bandeja          → fragmento de bandeja (polling 15s)
  GET  /c/<id>/                   → vista conversación (cabecera + mensajes + form)
  GET  /c/<id>/mensajes           → fragmento mensajes (polling 5s)
  POST /c/<id>/enviar             → crea mensaje (HTMX) y devuelve mensajes
  POST /c/<id>/leido              → marca leído (idempotente)
  GET  /nueva/                    → form para nueva conversación
  POST /nueva/                    → crea (1:1 o grupo) y redirige

  GET  /legacy/                   → bandeja vieja de Recados (compat)

Acceso: cualquier usuario con `recados.ver`. Estar en `participantes`
es requisito para abrir una conversación.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cuentas.models.usuario import Usuario
from lib.permisos import puede

from . import services_chat
from .models import Conversacion


def _sin_acceso():
    return HttpResponse("Sin acceso a Los Recados.", status=403)


def _gate(request):
    if not puede(request.user, "recados", "ver"):
        return _sin_acceso()
    return None


# ── Bandeja ──────────────────────────────────────────────────────────────────


def _datos_buzon_para(user):
    """S-LC-Feedback-V4: bloque de Buzón embebido en la bandeja de Recados.

    - Admin (puede ver_todos): lista de mensajes pendientes con link al detalle.
    - Empleado: form para escribir nuevo + sus propios mensajes recientes en lectura.
    """
    from buzon.models import MensajeBuzon
    from apps.buzon_empleado.forms import NuevoMensajeForm

    es_admin = puede(user, "buzon", "ver_todos")
    if es_admin:
        qs = (
            MensajeBuzon.objects.select_related("autor")
            .exclude(estado="archivado")
            .order_by("-prioridad", "-creado_en")[:10]
        )
        return {
            "buzon_es_admin": True,
            "buzon_mensajes": list(qs),
            "buzon_form": None,
        }
    return {
        "buzon_es_admin": False,
        "buzon_mensajes": list(
            MensajeBuzon.objects.filter(autor=user).order_by("-creado_en")[:5]
        ),
        "buzon_form": NuevoMensajeForm(),
    }


@login_required
def bandeja(request):
    if (r := _gate(request)) is not None:
        return r
    items = services_chat.mis_conversaciones(request.user)
    ctx = {
        "items": items,
        "puede_crear": puede(request.user, "recados", "crear"),
    }
    ctx.update(_datos_buzon_para(request.user))
    return render(request, "recados/chat_bandeja.html", ctx)


@login_required
def partial_bandeja(request):
    if (r := _gate(request)) is not None:
        return r
    items = services_chat.mis_conversaciones(request.user)
    return render(request, "recados/_chat_bandeja_lista.html", {"items": items})


# ── Conversación ─────────────────────────────────────────────────────────────


def _conv_o_404(request, pk):
    conv = Conversacion.objects.filter(pk=pk).prefetch_related("participantes").first()
    if conv is None or not conv.participantes.filter(pk=request.user.pk).exists():
        raise Http404("Conversación no encontrada.")
    return conv


@login_required
def conversacion(request, pk: int):
    if (r := _gate(request)) is not None:
        return r
    conv = _conv_o_404(request, pk)
    mensajes = list(conv.mensajes.select_related("autor").order_by("creado_en"))
    if mensajes:
        services_chat.marcar_leido_hasta(usuario=request.user, conversacion=conv, mensaje_id=mensajes[-1].pk)
    titulo = _titulo(conv, request.user)
    return render(request, "recados/chat_conversacion.html", {
        "conv": conv,
        "mensajes": mensajes,
        "titulo": titulo,
        "ultimo_id": mensajes[-1].pk if mensajes else 0,
    })


@login_required
def partial_mensajes(request, pk: int):
    """Devuelve sólo los mensajes NUEVOS desde `desde_id` (query param).
    Si no hay query, devuelve todos. HTMX hace polling cada 5s con
    `hx-vals` actualizando `desde_id`."""
    if (r := _gate(request)) is not None:
        return r
    conv = _conv_o_404(request, pk)
    desde = int(request.GET.get("desde_id") or 0)
    qs = conv.mensajes.select_related("autor").order_by("creado_en")
    if desde:
        qs = qs.filter(id__gt=desde)
    mensajes = list(qs)
    if mensajes:
        services_chat.marcar_leido_hasta(usuario=request.user, conversacion=conv, mensaje_id=mensajes[-1].pk)
    ultimo_id = mensajes[-1].pk if mensajes else desde
    return render(request, "recados/_chat_mensajes.html", {
        "mensajes": mensajes, "conv": conv, "ultimo_id": ultimo_id,
        "fragmento": True,
    })


@login_required
@require_http_methods(["POST"])
def enviar(request, pk: int):
    if (r := _gate(request)) is not None:
        return r
    if not puede(request.user, "recados", "crear"):
        return _sin_acceso()
    conv = _conv_o_404(request, pk)
    cuerpo = (request.POST.get("cuerpo") or "").strip()
    if not cuerpo:
        return HttpResponse(status=204)  # noop
    try:
        services_chat.enviar_mensaje(conversacion=conv, autor=request.user, cuerpo=cuerpo)
    except (ValueError, PermissionError) as exc:
        return HttpResponse(str(exc), status=400)
    # Respondemos sólo con el partial de mensajes nuevos (HTMX append).
    return partial_mensajes(request, pk)


@login_required
@require_http_methods(["POST"])
def marcar_leido(request, pk: int):
    if (r := _gate(request)) is not None:
        return r
    conv = _conv_o_404(request, pk)
    services_chat.marcar_leido_hasta(usuario=request.user, conversacion=conv)
    return HttpResponse(status=204)


# ── Nueva conversación ───────────────────────────────────────────────────────


@login_required
def nueva(request):
    if (r := _gate(request)) is not None:
        return r
    if not puede(request.user, "recados", "crear"):
        return _sin_acceso()

    if request.method == "POST":
        tipo = request.POST.get("tipo") or "directa"
        if tipo == "directa":
            destino_id = request.POST.get("destinatario")
            if not destino_id:
                messages.error(request, "Selecciona un destinatario.")
                return redirect("recados:nueva")
            otro = get_object_or_404(Usuario, pk=int(destino_id), is_active=True)
            if otro.pk == request.user.pk:
                messages.error(request, "No puedes abrir una conversación contigo mismo.")
                return redirect("recados:nueva")
            conv = services_chat.obtener_o_crear_directa(request.user, otro)
        else:
            nombre = (request.POST.get("nombre") or "").strip()
            ids = [int(i) for i in request.POST.getlist("participantes") if i.isdigit()]
            if not nombre:
                messages.error(request, "El grupo necesita un nombre.")
                return redirect("recados:nueva")
            try:
                conv = services_chat.crear_grupo(autor=request.user, nombre=nombre, participantes_ids=ids)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("recados:nueva")
        return redirect("recados:conversacion", pk=conv.pk)

    candidatos = Usuario.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by("nombre_completo")
    return render(request, "recados/chat_nueva.html", {"candidatos": candidatos})


# ── Helpers ──────────────────────────────────────────────────────────────────


def _titulo(conv: Conversacion, usuario) -> str:
    if conv.tipo == Conversacion.DIRECTA:
        otro = next((p for p in conv.participantes.all() if p.pk != usuario.pk), None)
        return (otro.nombre_completo or otro.email) if otro else "(sin participante)"
    return conv.nombre or f"Grupo #{conv.pk}"
