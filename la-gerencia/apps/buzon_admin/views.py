"""El Buzón (admin) — vista para super_admin/dueño."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from buzon.models import MensajeBuzon
from lib.permisos import requires_role
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import RespuestaAdminForm


@requires_role("super_admin", "dueno")
def lista(request):
    qs = MensajeBuzon.objects.select_related("autor")
    estado = request.GET.get("estado") or ""
    tipo = request.GET.get("tipo") or ""
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return render(request, "buzon_admin/lista.html", {
        "mensajes": qs,
        "estado_filtro": estado,
        "tipo_filtro": tipo,
    })


@requires_role("super_admin", "dueno")
@require_http_methods(["GET", "POST"])
def detalle(request, pk: int):
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    # Auto-marcar como leído al abrir un mensaje "nuevo".
    if request.method == "GET" and msg.estado == "nuevo":
        msg.estado = "leido"
        msg.save(update_fields=["estado", "actualizado_en"])
        emitir(EventoPortavoz(
            tipo="buzon.estado_cambiado",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={"mensaje_id": msg.pk, "estado": "leido"},
        ))

    if request.method == "POST":
        form = RespuestaAdminForm(request.POST, instance=msg)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.respuesta_publica and obj.estado in ("nuevo", "leido"):
                obj.estado = "respondido"
            if obj.respuesta_publica and not obj.respondido_en:
                obj.respondido_en = timezone.now()
                obj.respondido_por = request.user
            obj.save()
            if obj.respuesta_publica:
                emitir(EventoPortavoz(
                    tipo="buzon.respondido",
                    actor_id=request.user.pk,
                    actor_email=request.user.email,
                    payload={"mensaje_id": obj.pk, "autor_id": obj.autor_id},
                ))
            else:
                emitir(EventoPortavoz(
                    tipo="buzon.estado_cambiado",
                    actor_id=request.user.pk,
                    actor_email=request.user.email,
                    payload={"mensaje_id": obj.pk, "estado": obj.estado},
                ))
            messages.success(request, "Mensaje actualizado.")
            return redirect("buzon-admin-detalle", pk=msg.pk)
    else:
        form = RespuestaAdminForm(instance=msg)
    return render(request, "buzon_admin/detalle.html", {"mensaje": msg, "form": form})


@requires_role("super_admin", "dueno")
def exportar_a_claude(request, pk: int):
    """Devuelve el mensaje formateado en Markdown para pegar en una sesión de
    análisis. Texto plano, content-type para que el navegador no lo renderice."""
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    md = (
        f"# Buzón #{msg.pk} — {msg.get_tipo_display()}\n\n"
        f"**Autor:** {msg.autor.email} ({msg.autor.rol})  \n"
        f"**Fecha:** {msg.creado_en:%Y-%m-%d %H:%M}  \n"
        f"**Estado:** {msg.get_estado_display()}\n\n"
        f"## Asunto\n{msg.asunto}\n\n"
        f"## Cuerpo\n{msg.cuerpo}\n\n"
        f"## Nota interna (admin)\n{msg.nota_interna or '_(sin nota)_'}\n\n"
        f"## Respuesta pública\n{msg.respuesta_publica or '_(pendiente)_'}\n"
    )
    return HttpResponse(md, content_type="text/markdown; charset=utf-8")
