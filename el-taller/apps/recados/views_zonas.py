"""Zonas de Recados (S-Recados-V2 / C5c).

/recados/ se organiza en 3 zonas con tabs:
  - Chat        → views_chat.bandeja (lo de siempre)
  - Buzón       → zona_buzon: mis envíos al Buzón + sus respuestas
  - Actividad   → zona_actividad: menciones ("te taggearon") + actividad de
                  los proyectos del usuario (líder/asignado)
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from lib.permisos import puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto


def _gate(request):
    if not puede(request.user, "recados", "ver"):
        return HttpResponse("Sin acceso a Mensajes.", status=403)
    return None


# ── Mi Buzón (experiencia del usuario, S-Buzon-SuperAdmin) ───────────────────
# La bandeja de soporte (/buzon/*) es solo super_admin. Aquí el usuario ve y
# atiende SOLO sus propios tickets, reutilizando los componentes de filtro /
# búsqueda / marcar del Buzón pero sin ninguna acción de administración.


@login_required
def zona_buzon(request):
    """Mis mensajes al Buzón: lista propia con filtros + búsqueda + marcar."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.estados import estados_activos
    from buzon.lecturas import anotar_leido, contar_no_leidos
    from buzon.models import MensajeBuzon
    from buzon.tipos import tipos_activos

    user = request.user
    base = MensajeBuzon.objects.filter(autor=user)
    qs = base.select_related("autor").annotate(num_adjuntos=Count("adjuntos"))

    estado = request.GET.get("estado") or ""
    tipo = request.GET.get("tipo") or ""
    q = (request.GET.get("q") or "").strip()
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(asunto__icontains=q) | Q(cuerpo__icontains=q))
    qs = anotar_leido(qs, user).order_by("-creado_en")

    kpis = {
        "nuevos": base.filter(estado="nuevo").count(),
        "leidos": base.filter(estado="leido").count(),
        "respondidos": base.filter(estado="respondido").count(),
        "archivados": base.filter(estado="archivado").count(),
    }
    no_leidos_mio = contar_no_leidos(user, base)

    def _link(**overrides):
        cur = {"estado": estado, "tipo": tipo, "q": q}
        cur.update(overrides)
        params = {k: v for k, v in cur.items() if v}
        return "?" + urlencode(params) if params else "?"

    estado_chips = [{"label": "Todos", "link": _link(estado=""), "activo": not estado, "color": ""}]
    for e in estados_activos():
        estado_chips.append({
            "label": e["label"], "link": _link(estado=e["slug"]),
            "activo": estado == e["slug"], "color": e.get("color") or "",
        })
    tipo_chips = [{"label": "Todos", "link": _link(tipo=""), "activo": not tipo}]
    for t in tipos_activos():
        tipo_chips.append({"label": t["label"], "link": _link(tipo=t["slug"]), "activo": tipo == t["slug"]})

    def _kpi_link(filtro):
        return _link(estado="" if estado == filtro else filtro)

    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    qs_pag = urlencode({k: v for k, v in {"estado": estado, "tipo": tipo, "q": q}.items() if v})
    volver_qs = qs_pag
    if page_obj.number > 1:
        volver_qs = (f"{qs_pag}&" if qs_pag else "") + f"page={page_obj.number}"

    return render(request, "recados/buzon_lista.html", {
        "mensajes": page_obj,
        "page_obj": page_obj,
        "querystring_paginacion": qs_pag,
        "volver_qs": volver_qs,
        "estado_filtro": estado,
        "tipo_filtro": tipo,
        "q": q,
        "no_leidos_mio": no_leidos_mio,
        "kpis": kpis,
        "estado_chips": estado_chips,
        "tipo_chips": tipo_chips,
        "tiene_filtros": bool(estado or tipo or q),
        "kpi_links": {
            "nuevo": _kpi_link("nuevo"), "leido": _kpi_link("leido"),
            "respondido": _kpi_link("respondido"), "archivado": _kpi_link("archivado"),
        },
        "kpi_activos": {
            "nuevo": estado == "nuevo", "leido": estado == "leido",
            "respondido": estado == "respondido", "archivado": estado == "archivado",
        },
    })


@login_required
@require_http_methods(["GET", "POST"])
def buzon_nuevo(request):
    """Escribir al Buzón (cualquier usuario de Mensajes). Reemplaza /buzon/nuevo
    para los no-super_admin — el form vive bajo Mensajes."""
    if (r := _gate(request)) is not None:
        return r
    from apps.buzon_empleado.forms import NuevoMensajeForm
    from apps.buzon_empleado.views import _procesar_adjuntos_buzon

    from buzon.models import MensajeBuzon
    from lib.colador import colar_reporte

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
            _procesar_adjuntos_buzon(request, msg)
            emitir(EventoPortavoz(
                tipo="buzon.nuevo_mensaje",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"mensaje_id": msg.pk, "tipo": msg.tipo},
            ))
            from apps.taller_home.push_handlers import notificar_buzon_nuevo
            notificar_buzon_nuevo(msg, request.user)
            messages.success(request, "Mensaje enviado al Buzón. Gracias por escribirnos.")
            siguiente = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if siguiente and siguiente.startswith("/"):
                return redirect(siguiente)
            return redirect("recados:buzon_detalle", pk=msg.pk)
    else:
        form = NuevoMensajeForm(initial=inicial)
    return render(request, "recados/buzon_nuevo.html", {"form": form})


def _mi_mensaje(request, pk):
    """Obtiene un MensajeBuzon que pertenezca al usuario, o 404."""
    from buzon.models import MensajeBuzon
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    if msg.autor_id != request.user.pk:
        raise Http404
    return msg


@login_required
@require_http_methods(["GET"])
def buzon_detalle(request, pk: int):
    """Mi ticket: cuerpo + respuesta del equipo + UN solo hilo de conversación.
    Sin formularios de administración (decisión Oscar)."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.estados import label_de
    from buzon.lecturas import marcar_leido
    from buzon.models import ConfiguracionBuzon

    msg = _mi_mensaje(request, pk)
    marcar_leido(request.user, msg)

    info_buzon = [
        {"label": "Tipo", "value": msg.get_tipo_display()},
        {"label": "Enviado", "value": msg.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Estado", "value": label_de(msg.estado)},
    ]
    if msg.respondido_en:
        info_buzon.append({"label": "Respondido", "value": msg.respondido_en.strftime("%Y-%m-%d %H:%M")})

    comentarios = list(msg.comentarios.select_related("autor"))
    puede_comentar_hilo = ConfiguracionBuzon.obtener().empleado_puede_responder
    return render(request, "recados/buzon_detalle.html", {
        "mensaje": msg,
        "info_buzon": info_buzon,
        "comentarios": comentarios,
        "puede_comentar_hilo": puede_comentar_hilo,
        "comentar_url": reverse("recados:buzon_comentar", args=[msg.pk]),
    })


@login_required
@require_http_methods(["POST"])
def buzon_comentar(request, pk: int):
    """Responder en MI ticket. Respeta el toggle `empleado_puede_responder`."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.models import ConfiguracionBuzon, MensajeBuzonComentario

    msg = _mi_mensaje(request, pk)
    if not ConfiguracionBuzon.obtener().empleado_puede_responder:
        return HttpResponse("Solo el equipo puede responder en este ticket.", status=403)
    cuerpo = sanear_contexto((request.POST.get("cuerpo") or "").strip(), max_len=5000)
    if cuerpo:
        MensajeBuzonComentario.objects.create(mensaje=msg, autor=request.user, cuerpo=cuerpo)
        emitir(EventoPortavoz(
            tipo="buzon.comentario",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"mensaje_id": msg.pk},
        ))
        from apps.taller_home.push_handlers import notificar_buzon_comentario
        notificar_buzon_comentario(msg, request.user)
        messages.success(request, "Mensaje enviado.")
    else:
        messages.error(request, "Escribe algo antes de enviar.")
    return redirect("recados:buzon_detalle", pk=msg.pk)


@login_required
@require_http_methods(["POST"])
def buzon_toggle_leido(request, pk: int):
    """Marca MI mensaje como leído/no leído (por usuario)."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.lecturas import marcar_leido, marcar_no_leido
    from buzon.models import LecturaBuzon

    msg = _mi_mensaje(request, pk)
    if LecturaBuzon.objects.filter(usuario=request.user, mensaje=msg).exists():
        marcar_no_leido(request.user, msg)
        messages.success(request, "Marcado como no leído.")
    else:
        marcar_leido(request.user, msg)
        messages.success(request, "Marcado como leído.")
    volver = (request.POST.get("volver") or "").strip()
    destino = reverse("recados:zona_buzon") + (f"?{volver}" if volver else "")
    return redirect(destino)


@login_required
@require_http_methods(["POST"])
def buzon_masivo(request):
    """Marcar TODOS mis mensajes como leídos (por usuario)."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.models import LecturaBuzon, MensajeBuzon

    accion = (request.POST.get("accion") or "").strip()
    if accion == "marcar_todo_leido_mio":
        vis_ids = list(MensajeBuzon.objects.filter(autor=request.user).values_list("pk", flat=True))
        ya = set(LecturaBuzon.objects.filter(usuario=request.user).values_list("mensaje_id", flat=True))
        faltan = [LecturaBuzon(usuario=request.user, mensaje_id=i) for i in vis_ids if i not in ya]
        if faltan:
            LecturaBuzon.objects.bulk_create(faltan, ignore_conflicts=True)
        messages.success(request, f"{len(faltan)} marcado(s) como leído.")
    else:
        messages.error(request, "Acción desconocida.")
    return redirect("recados:zona_buzon")


@login_required
@require_http_methods(["GET"])
def buzon_adjunto(request, pk: int):
    """Descarga un adjunto de MI ticket desde Drive (proxy autenticado)."""
    if (r := _gate(request)) is not None:
        return r
    from urllib.parse import quote

    from buzon.models import MensajeBuzonAdjunto

    adj = get_object_or_404(MensajeBuzonAdjunto.objects.select_related("mensaje"), pk=pk)
    if adj.mensaje.autor_id != request.user.pk:
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


def _url_referencia(ref) -> str:
    """Deep-link al contenedor donde me mencionaron."""
    t, cid = ref.contenedor_tipo, ref.contenedor_id
    if t == "mensaje_chat":
        from .models import Mensaje
        conv = Mensaje.objects.filter(pk=cid).values_list("conversacion_id", flat=True).first()
        return f"/recados/c/{conv}/" if conv else ""
    if t == "recado":
        return f"/recados/legacy/{cid}/"
    if t in ("comentario_tarea", "comentario_proyecto"):
        from apps.el_pizarron.models import Comentario
        c = Comentario.objects.filter(pk=cid).select_related("tarea").first()
        if not c:
            return ""
        if c.proyecto_id:
            return f"/proyectos/{c.proyecto_id}/"
        if c.tarea_id and c.tarea.proyecto_id:
            return f"/proyectos/{c.tarea.proyecto_id}/"
    return ""


_ETIQUETA_FUENTE = {
    "mensaje_chat": "en un chat",
    "recado": "en un recado",
    "comentario_tarea": "en un comentario de tarea",
    "comentario_proyecto": "en un comentario de proyecto",
}


@login_required
def zona_actividad(request):
    """Menciones (te taggearon) + actividad de mis proyectos."""
    if (r := _gate(request)) is not None:
        return r
    from referencias.models import Referencia

    refs = list(
        Referencia.objects.filter(usuario=request.user, tipo="usuario")
        .order_by("-creado_en")[:50]
    )
    menciones = []
    for ref in refs:
        url = _url_referencia(ref)
        if not url:
            continue
        menciones.append({
            "fuente": _ETIQUETA_FUENTE.get(ref.contenedor_tipo, "en el sistema"),
            "url": url,
            "creado_en": ref.creado_en,
        })

    from apps.los_proyectos import servicios_actividad
    actividad = servicios_actividad.feed_para(request.user, limite=50)

    return render(request, "recados/zona_actividad.html", {
        "menciones": menciones,
        "actividad": actividad,
    })
