"""El Buzón unificado en El Taller (Pre-S2b.2).

Antes había dos apps: `buzon_admin` en Gerencia (super_admin/dueno veían
todos los mensajes con form de respuesta) y `buzon_empleado` en Taller
(empleado solo veía los suyos). Pre-S2b.2 las unifica: una sola bandeja
en Taller que adapta su contenido según `puede(user, "buzon", "ver_todos")`.

Permisos:
  buzon.ver_propios  → ve sus mensajes (todos los autenticados lo tienen)
  buzon.ver_todos    → ve TODOS los mensajes + form de respuesta (admin)
  buzon.responder    → puede escribir respuesta_admin
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from buzon.models import MensajeBuzon
from lib.colador import colar_reporte
from lib.permisos import puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto

from .forms import NuevoMensajeForm, RespuestaAdminForm

# ── Lista unificada ──────────────────────────────────────────────────────────


@login_required
def lista(request):
    """Bandeja adaptativa: admin (ver_todos) o empleado (ver_propios)."""
    user = request.user
    es_admin_buzon = puede(user, "buzon", "ver_todos")
    qs = MensajeBuzon.objects.select_related("autor")
    if not es_admin_buzon:
        qs = qs.filter(autor=user)

    # Filtros admin
    estado = request.GET.get("estado") or ""
    tipo = request.GET.get("tipo") or ""
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)

    base = MensajeBuzon.objects.all() if es_admin_buzon else MensajeBuzon.objects.filter(autor=user)
    kpis = {
        "nuevos": base.filter(estado="nuevo").count(),
        "leidos": base.filter(estado="leido").count(),
        "respondidos": base.filter(estado="respondido").count(),
        "archivados": base.filter(estado="archivado").count(),
    }
    cabeceras = [{"label": "#"}, {"label": "Prioridad", "align": "center"}]
    if es_admin_buzon:
        cabeceras.append({"label": "Autor"})
    cabeceras += [
        {"label": "Tipo"},
        {"label": "Asunto"},
        {"label": "Estado"},
        {"label": "Recibido"},
    ]
    return render(request, "buzon/lista.html", {
        "mensajes": qs,
        "es_admin_buzon": es_admin_buzon,
        "estado_filtro": estado,
        "tipo_filtro": tipo,
        "kpis": kpis,
        "cabeceras_buzon": cabeceras,
    })


@login_required
@require_http_methods(["GET", "POST"])
def detalle(request, pk: int):
    """Detalle adaptativo: admin ve todo + form respuesta; empleado solo si es autor."""
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    user = request.user
    es_admin_buzon = puede(user, "buzon", "ver_todos")
    puede_responder = puede(user, "buzon", "responder")

    # Si no es admin, sólo el autor puede verlo.
    if not es_admin_buzon and msg.autor_id != user.pk:
        raise Http404

    # Auto-marcar como leído al abrir un mensaje "nuevo" (solo admin).
    if request.method == "GET" and es_admin_buzon and msg.estado == "nuevo":
        msg.estado = "leido"
        msg.save(update_fields=["estado", "actualizado_en"])
        emitir(EventoPortavoz(
            tipo="buzon.estado_cambiado",
            actor_id=user.pk, actor_email=user.email,
            payload={"mensaje_id": msg.pk, "estado": "leido"},
        ))

    form = None
    if puede_responder:
        if request.method == "POST":
            form = RespuestaAdminForm(request.POST, instance=msg)
            if form.is_valid():
                m = form.save(commit=False)
                m.respondido_en = timezone.now()
                m.respondido_por = user
                if not m.estado or m.estado in ("nuevo", "leido"):
                    m.estado = "respondido"
                m.save()
                emitir(EventoPortavoz(
                    tipo="buzon.respondido",
                    actor_id=user.pk, actor_email=user.email,
                    payload={"mensaje_id": m.pk},
                ))
                messages.success(request, "Respuesta guardada.")
                return redirect("buzon-detalle", pk=m.pk)
        else:
            form = RespuestaAdminForm(instance=msg)

    from django.urls import reverse
    info_buzon = [
        {"label": "Tipo", "value": msg.get_tipo_display()},
        {"label": "Autor", "value": msg.autor.email},
        {"label": "Recibido", "value": msg.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Estado", "value": msg.get_estado_display()},
    ]
    if msg.respondido_en:
        info_buzon.append({"label": "Respondido", "value": msg.respondido_en.strftime("%Y-%m-%d %H:%M")})
    return render(request, "buzon/detalle.html", {
        "mensaje": msg, "form": form,
        "es_admin_buzon": es_admin_buzon,
        "puede_responder": puede_responder,
        "info_buzon": info_buzon,
        "breadcrumb_items": [
            {"url": reverse("buzon-lista"), "label": "El Buzón"},
            {"label": f"#{msg.pk}"},
        ],
        "back_url": reverse("buzon-lista"),
        "back_label": "El Buzón",
    })


@login_required
@require_http_methods(["GET", "POST"])
def nuevo(request):
    inicial = {
        "tipo": request.GET.get("tipo") or "sugerencia",
        "asunto": request.GET.get("asunto") or "",
        "cuerpo": request.GET.get("cuerpo") or "",
    }
    if request.method == "POST":
        form = NuevoMensajeForm(request.POST)
        if form.is_valid():
            msg: MensajeBuzon = form.save(commit=False)
            msg.autor = request.user
            if msg.tipo == "problema":
                msg.cuerpo = colar_reporte(msg.cuerpo)[:5000]
            else:
                msg.cuerpo = sanear_contexto(msg.cuerpo, max_len=5000)
            msg.asunto = sanear_contexto(msg.asunto, max_len=200) or msg.asunto[:200]
            msg.save()
            emitir(EventoPortavoz(
                tipo="buzon.nuevo_mensaje",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"mensaje_id": msg.pk, "tipo": msg.tipo},
            ))
            from apps.taller_home.push_handlers import notificar_buzon_nuevo
            notificar_buzon_nuevo(msg, request.user)
            messages.success(request, "Mensaje enviado al Buzón. Gracias por escribirnos.")
            return redirect("buzon-lista")
    else:
        form = NuevoMensajeForm(initial=inicial)
    return render(request, "buzon/nuevo.html", {"form": form})


@login_required
def exportar_a_claude(request, pk: int):
    """Solo admins (buzon.ver_todos). Mantiene comportamiento del antiguo buzon_admin."""
    if not puede(request.user, "buzon", "ver_todos"):
        return HttpResponse("Sin acceso.", status=403)
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    contenido = (
        f"# Buzón #{msg.pk} — {msg.tipo}\n\n"
        f"**Asunto:** {msg.asunto}\n\n"
        f"**Autor:** {msg.autor.email}\n\n"
        f"**Cuerpo:**\n\n{msg.cuerpo}\n"
    )
    if msg.respuesta_publica:
        contenido += f"\n**Respuesta:**\n\n{msg.respuesta_publica}\n"
    if msg.nota_interna:
        contenido += f"\n**Nota interna:**\n\n{msg.nota_interna}\n"
    resp = HttpResponse(contenido, content_type="text/markdown; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="buzon-{msg.pk}.md"'
    return resp


# ── Compatibilidad con URLs viejas — redirigir a las nuevas ─────────────────


@login_required
def mios_lista(request):
    return redirect("buzon-lista")


@login_required
def mios_detalle(request, pk: int):
    return redirect("buzon-detalle", pk=pk)
