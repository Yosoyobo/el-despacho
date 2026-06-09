"""Buzón unificado en El Taller (Pre-S2b.2).

Antes había dos apps: `buzon_admin` en Gerencia (super_admin/dueno veían
todos los mensajes con form de respuesta) y `buzon_empleado` en Taller
(empleado solo veía los suyos). Pre-S2b.2 las unifica: una sola bandeja
en Taller que adapta su contenido según `puede(user, "buzon", "ver_todos")`.

Permisos:
  buzon.ver_propios  → ve sus mensajes (todos los autenticados lo tienen)
  buzon.ver_todos    → ve TODOS los mensajes + form de respuesta (admin)
  buzon.responder    → puede escribir respuesta_admin
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from buzon.estados import estados_activos, label_de
from buzon.models import MensajeBuzon
from lib.colador import colar_reporte
from lib.permisos import es_admin, puede
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
    qs = MensajeBuzon.objects.select_related("autor").annotate(num_adjuntos=Count("adjuntos"))
    if not es_admin_buzon:
        qs = qs.filter(autor=user)

    # Filtros admin
    estado = request.GET.get("estado") or ""
    tipo = request.GET.get("tipo") or ""
    q = (request.GET.get("q") or "").strip()
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(asunto__icontains=q) | Q(cuerpo__icontains=q) | Q(autor__email__icontains=q))

    # S-Chalanes-UX #3: lectura POR USUARIO. Anotamos cada mensaje con
    # `leido_para_mi` (negrita si no) y contamos los no leídos del usuario.
    from buzon.lecturas import anotar_leido, contar_no_leidos
    qs = anotar_leido(qs, user)

    # Orden — selector prioridad ↔ fecha. C1 S-LC-Feedback-V6: default ahora
    # es FECHA (lo más reciente arriba) por pedido de LC — antes era prioridad.
    orden = request.GET.get("orden") or "fecha"
    if orden == "prioridad":
        qs = qs.order_by("-prioridad", "-creado_en")
    else:
        orden = "fecha"
        qs = qs.order_by("-creado_en")

    base = MensajeBuzon.objects.all() if es_admin_buzon else MensajeBuzon.objects.filter(autor=user)
    kpis = {
        "nuevos": base.filter(estado="nuevo").count(),
        "leidos": base.filter(estado="leido").count(),
        "respondidos": base.filter(estado="respondido").count(),
        "archivados": base.filter(estado="archivado").count(),
    }
    no_leidos_mio = contar_no_leidos(user, base)
    cabeceras = []
    if es_admin_buzon:
        cabeceras.append({"label": "", "clase_th": "w-8"})  # checkbox col
    cabeceras += [{"label": "#"}, {"label": "Prioridad", "align": "center"}]
    if es_admin_buzon:
        cabeceras.append({"label": "Autor"})
    cabeceras += [
        {"label": "Tipo"},
        {"label": "Asunto"},
        {"label": "Estado"},
        {"label": "Recibido"},
    ]
    # Toggle: KPI cards clickeables. Cuando el filtro está activo, el link
    # apunta a "" (sin filtro); cuando no, aplica el filtro. `orden` solo se
    # incluye si no es el default (fecha), para mantener las URLs limpias.
    from urllib.parse import quote
    def _kpi_link(filtro):
        partes = []
        if estado != filtro:
            partes.append(f"estado={filtro}")
        if tipo:
            partes.append(f"tipo={tipo}")
        if q:
            partes.append(f"q={quote(q)}")
        if orden and orden != "fecha":
            partes.append(f"orden={orden}")
        return "?" + "&".join(partes) if partes else "?"
    # Querystring base para preservar filtros + orden en links del header
    def _qs_con_orden(nuevo_orden: str) -> str:
        partes = []
        if estado:
            partes.append(f"estado={estado}")
        if tipo:
            partes.append(f"tipo={tipo}")
        if q:
            partes.append(f"q={quote(q)}")
        if nuevo_orden != "fecha":
            partes.append(f"orden={nuevo_orden}")
        return "?" + "&".join(partes) if partes else "?"

    # C1 S-LC-Feedback-V6: querystring de los filtros activos. Se cuelga de
    # cada fila como `?volver=…` para que el detalle pueda regresar al listado
    # con el mismo filtro aplicado (el repo no preservaba filtros al volver).
    volver_partes = []
    if estado:
        volver_partes.append(f"estado={estado}")
    if tipo:
        volver_partes.append(f"tipo={tipo}")
    if q:
        volver_partes.append(f"q={quote(q)}")
    if orden and orden != "fecha":
        volver_partes.append(f"orden={orden}")
    volver_qs = "&".join(volver_partes)

    return render(request, "buzon/lista.html", {
        "mensajes": qs,
        "es_admin_buzon": es_admin_buzon,
        "estado_filtro": estado,
        "tipo_filtro": tipo,
        "q": q,
        "no_leidos_mio": no_leidos_mio,
        "orden_actual": orden,
        "volver_qs": volver_qs,
        "link_orden_prioridad": _qs_con_orden("prioridad"),
        "link_orden_fecha": _qs_con_orden("fecha"),
        "kpis": kpis,
        "estados_disponibles": estados_activos(),
        "cabeceras_buzon": cabeceras,
        "kpi_links": {
            "nuevo": _kpi_link("nuevo"),
            "leido": _kpi_link("leido"),
            "respondido": _kpi_link("respondido"),
            "archivado": _kpi_link("archivado"),
        },
        "kpi_activos": {
            "nuevo": estado == "nuevo",
            "leido": estado == "leido",
            "respondido": estado == "respondido",
            "archivado": estado == "archivado",
        },
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

    # C1 S-LC-Feedback-V6: `volver` trae el querystring de filtros del listado
    # para regresar con el mismo filtro aplicado.
    volver = (request.GET.get("volver") or "").strip()
    # S-LC-Buzon: master-detail. Si el request es HTMX, devolvemos sólo el panel
    # de lectura (buzon/_pane.html) para inyectar en #buzon-pane sin navegar.
    es_htmx = request.headers.get("HX-Request") == "true"

    # S-Chalanes-UX #3: marca leído POR USUARIO al abrir (todos, como email).
    if request.method == "GET":
        from buzon.lecturas import marcar_leido
        marcar_leido(user, msg)

    # Auto-marcar el estado GLOBAL como "leido" al abrir un mensaje "nuevo"
    # (solo admin) — flujo de atención del equipo, independiente del leído
    # por-usuario.
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
                if es_htmx:
                    # Re-render del panel con form fresco y mensaje actualizado.
                    msg = m
                    form = RespuestaAdminForm(instance=msg)
                else:
                    messages.success(request, "Respuesta guardada.")
                    destino = reverse("buzon-detalle", args=[m.pk])
                    if volver:
                        destino += "?" + urlencode({"volver": volver})
                    return redirect(destino)
        else:
            form = RespuestaAdminForm(instance=msg)

    info_buzon = [
        {"label": "Tipo", "value": msg.get_tipo_display()},
        {"label": "Autor", "value": msg.autor.email},
        {"label": "Recibido", "value": msg.creado_en.strftime("%Y-%m-%d %H:%M")},
        {"label": "Estado", "value": label_de(msg.estado)},
    ]
    if msg.respondido_en:
        info_buzon.append({"label": "Respondido", "value": msg.respondido_en.strftime("%Y-%m-%d %H:%M")})
    # C1: regresa al listado con el filtro previo (si vino `volver`).
    url_lista = reverse("buzon-lista") + (f"?{volver}" if volver else "")
    if es_htmx:
        return render(request, "buzon/_pane.html", {
            "mensaje": msg, "form": form,
            "es_admin_buzon": es_admin_buzon,
            "puede_responder": puede_responder,
            "info_buzon": info_buzon,
        })
    return render(request, "buzon/detalle.html", {
        "mensaje": msg, "form": form,
        "es_admin_buzon": es_admin_buzon,
        "puede_responder": puede_responder,
        "info_buzon": info_buzon,
        "breadcrumb_items": [
            {"url": url_lista, "label": "Buzón"},
            {"label": f"#{msg.pk}"},
        ],
        "back_url": url_lista,
        "back_label": "Buzón",
    })


def _procesar_adjuntos_buzon(request, msg) -> None:
    """Sube los archivos del mensaje del Buzón a Drive y crea las filas.

    Fallback gracioso: si Drive cae, el mensaje ya quedó guardado; el adjunto
    simplemente no se crea (avisamos con un warning)."""
    archivos = request.FILES.getlist("adjuntos")
    if not archivos:
        return
    from buzon.models import MensajeBuzonAdjunto
    from lib.adjuntos import subir
    subidos = 0
    for archivo in archivos:
        res = subir(archivo, subcarpeta="Buzón")
        if res.ok and res.data:
            MensajeBuzonAdjunto.objects.create(
                mensaje=msg,
                drive_file_id=res.data["id"],
                nombre=res.data.get("name") or archivo.name,
                mime_type=res.data.get("mimeType") or getattr(archivo, "content_type", "") or "",
                tamano_bytes=int(res.data.get("size") or getattr(archivo, "size", 0) or 0),
                subido_por=request.user,
            )
            subidos += 1
        else:
            messages.warning(request, f"Adjunto no subido: {res.error}")


@login_required
@require_http_methods(["POST"])
def toggle_leido(request, pk: int):
    """Alterna leído/no leído POR USUARIO (S-Chalanes-UX #3). Cualquier usuario
    sobre un mensaje que pueda ver."""
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    if not puede(request.user, "buzon", "ver_todos") and msg.autor_id != request.user.pk:
        raise Http404
    from buzon.lecturas import marcar_leido, marcar_no_leido
    from buzon.models import LecturaBuzon
    ya = LecturaBuzon.objects.filter(usuario=request.user, mensaje=msg).exists()
    if ya:
        marcar_no_leido(request.user, msg)
        messages.success(request, "Marcado como no leído.")
    else:
        marcar_leido(request.user, msg)
        messages.success(request, "Marcado como leído.")
    volver = (request.POST.get("volver") or "").strip()
    destino = reverse("buzon-lista") + (f"?{volver}" if volver else "")
    return redirect(destino)


@login_required
@require_http_methods(["GET"])
def adjunto_descargar(request, pk: int):
    """Sirve un adjunto del Buzón desde Drive (proxy autenticado). Lo bajan el
    autor del mensaje o los admins del Buzón (ver_todos)."""
    from urllib.parse import quote

    from buzon.models import MensajeBuzonAdjunto

    adj = get_object_or_404(MensajeBuzonAdjunto.objects.select_related("mensaje"), pk=pk)
    user = request.user
    if not puede(user, "buzon", "ver_todos") and adj.mensaje.autor_id != user.pk:
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
            _procesar_adjuntos_buzon(request, msg)
            emitir(EventoPortavoz(
                tipo="buzon.nuevo_mensaje",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"mensaje_id": msg.pk, "tipo": msg.tipo},
            ))
            from apps.taller_home.push_handlers import notificar_buzon_nuevo
            notificar_buzon_nuevo(msg, request.user)
            messages.success(request, "Mensaje enviado al Buzón. Gracias por escribirnos.")
            # S-LC-Feedback-V4: si vino con ?next= (p.ej. desde el embed en /recados/),
            # respetamos esa URL para volver al contexto original.
            siguiente = (request.POST.get("next") or request.GET.get("next") or "").strip()
            if siguiente and siguiente.startswith("/"):
                return redirect(siguiente)
            return redirect("buzon-lista")
    else:
        form = NuevoMensajeForm(initial=inicial)
    return render(request, "buzon/nuevo.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def accion_masiva(request):
    """POST /buzon/masivo — acción sobre múltiples mensajes a la vez.

    Acciones de lectura POR USUARIO (cualquier autenticado, S-Chalanes-UX #3):
      - marcar_leido_mio / marcar_no_leido_mio

    Acciones de estado GLOBAL (solo admin con buzon.ver_todos):
      - estado_leido / estado_respondido / estado_archivado / estado_nuevo
      - eliminar (borra de DB; sólo super_admin/dueno).

    Espera POST con `ids[]` lista de PKs y `accion` string.
    """
    ids = request.POST.getlist("ids")
    accion = (request.POST.get("accion") or "").strip()
    if not ids or not accion:
        messages.error(request, "Selecciona al menos un mensaje y una acción.")
        return redirect("buzon-lista")
    try:
        ids_int = [int(i) for i in ids]
    except ValueError:
        messages.error(request, "IDs inválidos.")
        return redirect("buzon-lista")

    # ── Lectura por usuario (todos los roles) ──────────────────────────────
    if accion in ("marcar_leido_mio", "marcar_no_leido_mio"):
        from buzon.models import LecturaBuzon
        # Sólo sobre mensajes visibles para el usuario.
        visibles = MensajeBuzon.objects.filter(pk__in=ids_int)
        if not puede(request.user, "buzon", "ver_todos"):
            visibles = visibles.filter(autor=request.user)
        vis_ids = list(visibles.values_list("pk", flat=True))
        if accion == "marcar_leido_mio":
            LecturaBuzon.objects.bulk_create(
                [LecturaBuzon(usuario=request.user, mensaje_id=i) for i in vis_ids],
                ignore_conflicts=True)
            messages.success(request, f"{len(vis_ids)} marcado(s) como leído.")
        else:
            LecturaBuzon.objects.filter(usuario=request.user, mensaje_id__in=vis_ids).delete()
            messages.success(request, f"{len(vis_ids)} marcado(s) como no leído.")
        return redirect("buzon-lista")

    # ── Estado global / eliminar (solo admin) ──────────────────────────────
    if not puede(request.user, "buzon", "ver_todos"):
        return HttpResponse("Sin acceso.", status=403)

    qs = MensajeBuzon.objects.filter(pk__in=ids_int)
    n = qs.count()
    if accion == "eliminar":
        if not es_admin(request.user):
            return HttpResponse("Solo super_admin o dueño pueden eliminar.", status=403)
        # Emite evento antes de borrar.
        for m in qs:
            emitir(EventoPortavoz(
                tipo="buzon.eliminado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"mensaje_id": m.pk, "asunto": m.asunto},
            ))
        qs.delete()
        messages.success(request, f"{n} mensaje{'s' if n != 1 else ''} eliminado{'s' if n != 1 else ''}.")
    elif accion.startswith("estado_"):
        nuevo_estado = accion.removeprefix("estado_")
        # S-Buzon-Estados-V1: válido si es un estado activo configurado o uno
        # de los 4 base del sistema (que siempre existen).
        validos = {e["slug"] for e in estados_activos()} | {"nuevo", "leido", "respondido", "archivado"}
        if nuevo_estado not in validos:
            messages.error(request, "Estado inválido.")
            return redirect("buzon-lista")
        qs.update(estado=nuevo_estado, actualizado_en=timezone.now())
        for pk in ids_int:
            emitir(EventoPortavoz(
                tipo="buzon.estado_cambiado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"mensaje_id": pk, "estado": nuevo_estado, "masivo": True},
            ))
        messages.success(request, f"{n} mensaje{'s' if n != 1 else ''} marcado{'s' if n != 1 else ''} como «{nuevo_estado}».")
    else:
        messages.error(request, "Acción desconocida.")
    return redirect("buzon-lista")


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
