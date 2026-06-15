"""Buzón (admin) — vista para super_admin/dueño."""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from buzon.models import MensajeBuzon
from lib.permisos import requiere_permiso
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import RespuestaAdminForm


@requiere_permiso("buzon", "ver_todos")
def lista(request):
    qs = MensajeBuzon.objects.select_related("autor")
    estado = request.GET.get("estado") or ""
    tipo = request.GET.get("tipo") or ""
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)

    # Orden — C1 S-LC-Feedback-V6: selector prioridad ↔ fecha, default FECHA
    # (alineado con el Buzón del Taller).
    orden = request.GET.get("orden") or "fecha"
    if orden == "prioridad":
        qs = qs.order_by("-prioridad", "-creado_en")
    else:
        orden = "fecha"
        qs = qs.order_by("-creado_en")

    def _qs_con_orden(nuevo_orden: str) -> str:
        partes = []
        if estado:
            partes.append(f"estado={estado}")
        if tipo:
            partes.append(f"tipo={tipo}")
        if nuevo_orden != "fecha":
            partes.append(f"orden={nuevo_orden}")
        return "?" + "&".join(partes) if partes else "?"

    volver_partes = []
    if estado:
        volver_partes.append(f"estado={estado}")
    if tipo:
        volver_partes.append(f"tipo={tipo}")
    if orden and orden != "fecha":
        volver_partes.append(f"orden={orden}")
    volver_qs = "&".join(volver_partes)

    from django.db.models import Count

    from lib.graficas import donut_desde_conteo
    base = MensajeBuzon.objects.all()
    kpis = {
        "nuevos": base.filter(estado="nuevo").count(),
        "leidos": base.filter(estado="leido").count(),
        "respondidos": base.filter(estado="respondido").count(),
        "archivados": base.filter(estado="archivado").count(),
    }
    por_tipo = dict(base.values_list("tipo").annotate(c=Count("id")).values_list("tipo", "c"))
    from buzon.estados import estados_activos
    from buzon.tipos import tipos_activos
    return render(request, "buzon_admin/lista.html", {
        "mensajes": qs,
        "estado_filtro": estado,
        "tipo_filtro": tipo,
        # S-LC-Feedback-V10: filtros dinámicos — todo estado/tipo activo del
        # catálogo aparece aquí en cuanto se crea (igual que el Buzón del Taller).
        "estados_disponibles": estados_activos(),
        "tipos_disponibles": tipos_activos(),
        "orden_actual": orden,
        "volver_qs": volver_qs,
        "link_orden_prioridad": _qs_con_orden("prioridad"),
        "link_orden_fecha": _qs_con_orden("fecha"),
        "kpis": kpis,
        "donut_tipos_json": donut_desde_conteo(por_tipo),
        "cabeceras_buzon_admin": [
            {"label": "#"},
            {"label": "Prioridad", "align": "center"},
            {"label": "Autor"},
            {"label": "Tipo"},
            {"label": "Asunto"},
            {"label": "Estado"},
            {"label": "Recibido"},
        ],
    })


@requiere_permiso("buzon", "ver_todos")
@require_http_methods(["GET", "POST"])
def detalle(request, pk: int):
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    volver = (request.GET.get("volver") or "").strip()
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
            from urllib.parse import urlencode as _urlencode

            from django.urls import reverse as _reverse
            destino = _reverse("buzon-admin-detalle", args=[msg.pk])
            if volver:
                destino += "?" + _urlencode({"volver": volver})
            return redirect(destino)
    else:
        form = RespuestaAdminForm(instance=msg)
    from django.urls import reverse
    info_buzon = [
        {"label": "Tipo", "value": msg.get_tipo_display()},
        {"label": "Prioridad", "value": f"{msg.prioridad}/10"},
        {"label": "Autor", "value": msg.autor.email},
        {"label": "Recibido", "value": msg.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Estado", "value": msg.get_estado_display()},
    ]
    if msg.respondido_en:
        info_buzon.append({"label": "Respondido", "value": msg.respondido_en.strftime("%Y-%m-%d %H:%M")})
    url_lista = reverse("buzon-admin-lista") + (f"?{volver}" if volver else "")
    return render(request, "buzon_admin/detalle.html", {
        "mensaje": msg, "form": form,
        "info_buzon": info_buzon,
        "breadcrumb_items": [
            {"url": url_lista, "label": "Buzón"},
            {"label": f"#{msg.pk}"},
        ],
        "back_url": url_lista,
        "back_label": "Buzón",
    })


@requiere_permiso("buzon", "ver_todos")
@require_http_methods(["GET"])
def adjunto_descargar(request, pk: int):
    """Sirve un adjunto del Buzón desde Drive (proxy autenticado para admins).

    La Gerencia tiene su propio proxy: la URL `buzon-adjunto` del Taller no
    resuelve aquí (otro urlconf) y la sesión es `gerencia_session`, no
    `taller_session`. Mismo patrón que el proxy del empleado, gateado a
    super_admin/dueño.
    """
    from urllib.parse import quote

    from buzon.models import MensajeBuzonAdjunto

    adj = get_object_or_404(MensajeBuzonAdjunto.objects.select_related("mensaje"), pk=pk)

    from lib.google_drive import drive
    try:
        contenido, mime, nombre = drive.descargar(adj.drive_file_id)
    except Exception:  # noqa: BLE001
        raise Http404("No se pudo obtener el archivo de Drive.") from None

    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    disposicion = "inline" if (mime or "").startswith(("image/", "application/pdf")) else "attachment"
    resp["Content-Disposition"] = f"{disposicion}; filename*=UTF-8''{quote(nombre)}"
    return resp


@requiere_permiso("buzon", "ver_todos")
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
