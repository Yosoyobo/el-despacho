"""Vistas de Recados (S2b.1).

Endpoints:
  /recados/             GET  → bandeja con pestañas tab=recibidos|enviados|menciones|no_leidos
  /recados/nuevo/       GET/POST
  /recados/<id>/        GET → detalle (marca leído implícito)
  /recados/<id>/editar/ GET/POST (solo autor con recados.editar_propios)
  /recados/<id>/leido/  POST (idempotente)

Cualquier endpoint sin `recados.ver` → 403. Detalle al que el usuario no
tiene relación devuelve 404 (no revela existencia).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from cuentas.models.usuario import Usuario
from lib.permisos import puede
from lib.sanear import sanear_contexto

from . import services
from .forms import RecadoForm
from .models import Recado, RecadoAdjunto, RecadoDestinatario, RecadoGrupo, RecadoVersion

UMBRAL_CONFIRMACION = 5


def _sin_acceso():
    return HttpResponse("Sin acceso a Recados.", status=403)


def _procesar_adjuntos(request, recado, user) -> None:
    """Sube los archivos del form a Drive y crea las filas RecadoAdjunto.

    Fallback gracioso: si Drive cae o un archivo es inválido, el recado ya
    quedó enviado; sólo avisamos con messages y seguimos.
    """
    if not puede(user, "recados", "adjuntar_drive"):
        return
    archivos = request.FILES.getlist("adjuntos")
    if not archivos:
        return

    from lib.adjuntos import subir

    subidos = 0
    for archivo in archivos:
        res = subir(archivo, subcarpeta="Los Recados")
        if res.ok and res.data:
            RecadoAdjunto.objects.create(
                recado=recado,
                drive_file_id=res.data["id"],
                nombre=res.data.get("name") or archivo.name,
                mime_type=res.data.get("mimeType") or getattr(archivo, "content_type", "") or "",
                tamano_bytes=int(res.data.get("size") or getattr(archivo, "size", 0) or 0),
                subido_por=user,
            )
            subidos += 1
        else:
            messages.warning(request, f"Adjunto no subido: {res.error}")
    if subidos:
        messages.success(request, f"{subidos} adjunto(s) guardado(s) en Drive.")


# ── Bandeja ──────────────────────────────────────────────────────────────────


@login_required
def bandeja(request):
    user = request.user
    if not puede(user, "recados", "ver"):
        return _sin_acceso()

    tab = (request.GET.get("tab") or "recibidos").lower()
    if tab not in {"recibidos", "enviados", "menciones", "no_leidos"}:
        tab = "recibidos"

    qs = Recado.objects.select_related("autor").order_by("-creado_en").distinct()

    if tab == "recibidos":
        qs = qs.filter(destinatarios__usuario=user)
    elif tab == "enviados":
        qs = qs.filter(autor=user)
    elif tab == "menciones":
        slug = getattr(user, "slug", None) or ""
        if not slug:
            qs = qs.none()
        else:
            token = f"@{slug}"
            qs = qs.filter(cuerpo__icontains=token).exclude(
                destinatarios__usuario=user
            ).exclude(autor=user)
    elif tab == "no_leidos":
        qs = qs.filter(destinatarios__usuario=user, destinatarios__leido_en__isnull=True)

    paginator = Paginator(qs, 25)
    pagina = paginator.get_page(request.GET.get("p") or 1)

    # KPIs hero (siempre sobre el usuario, independientes del tab actual).
    todos = Recado.objects.distinct()
    kpis = {
        "recibidos": todos.filter(destinatarios__usuario=user).count(),
        "enviados": todos.filter(autor=user).count(),
        "no_leidos": todos.filter(destinatarios__usuario=user, destinatarios__leido_en__isnull=True).count(),
    }
    slug = getattr(user, "slug", None) or ""
    kpis["menciones"] = (
        todos.filter(cuerpo__icontains=f"@{slug}").exclude(autor=user).count() if slug else 0
    )
    return render(request, "recados/bandeja.html", {
        "pagina": pagina,
        "recados": pagina.object_list,
        "tab": tab,
        "puede_crear": puede(user, "recados", "crear"),
        "kpis": kpis,
    })


# ── Detalle ──────────────────────────────────────────────────────────────────


@login_required
@require_http_methods(["GET"])
def detalle(request, pk: int):
    user = request.user
    if not puede(user, "recados", "ver"):
        return _sin_acceso()

    recado = Recado.objects.select_related("autor").filter(pk=pk).first()
    if recado is None or not services.puede_ver_recado(user, recado):
        raise Http404("Recado no encontrado.")

    # Marca leído implícito.
    fila = RecadoDestinatario.objects.filter(recado=recado, usuario=user).first()
    if fila and fila.leido_en is None:
        fila.leido_en = timezone.now()
        fila.save(update_fields=["leido_en"])
        services.emitir_leido(recado, user)

    destinatarios = list(
        RecadoDestinatario.objects.filter(recado=recado)
        .select_related("usuario")
        .order_by("usuario__nombre_completo")
    )
    versiones = list(
        RecadoVersion.objects.filter(recado=recado)
        .select_related("editado_por")
        .order_by("-version")
    )

    from django.urls import reverse
    from django.utils.html import format_html
    puede_ed = recado.autor_id == user.pk and puede(user, "recados", "editar_propios")
    info_recado = [
        {"label": "Autor", "value": recado.autor.nombre_completo or recado.autor.email if recado.autor else "—"},
        {"label": "Enviado", "value": recado.creado_en.strftime("%d %b %Y %H:%M")},
        {"label": "Destinatarios", "value": str(len(destinatarios))},
    ]
    if recado.editado:
        info_recado.append({"label": "Versión", "value": f"v{recado.version_actual} (editado)"})
    action_bar_acciones = format_html(
        '<a href="{}" class="btn-secundario">← Bandeja</a>'
        '<a href="{}?responder={}" class="btn-secundario">Responder</a>',
        reverse("recados:legacy_bandeja"), reverse("recados:legacy_nuevo"), recado.pk,
    )
    if puede_ed:
        action_bar_acciones = format_html(
            '{}<a href="{}" class="btn-primario">Editar</a>',
            action_bar_acciones,
            reverse("recados:legacy_editar", args=[recado.pk]),
        )
    return render(request, "recados/detalle.html", {
        "recado": recado,
        "destinatarios": destinatarios,
        "versiones": versiones,
        "puede_editar": puede_ed,
        "info_recado": info_recado,
        "action_bar_acciones": action_bar_acciones,
        "breadcrumb_items": [
            {"url": reverse("recados:legacy_bandeja"), "label": "Recados (legacy)"},
            {"label": f"#{recado.pk}"},
        ],
        "back_url": reverse("recados:legacy_bandeja"),
        "back_label": "Bandeja legacy",
    })


# ── Nuevo ────────────────────────────────────────────────────────────────────


def _grupos_disponibles():
    return list(RecadoGrupo.objects.exclude(tipo="dinamico").order_by("nombre_legible"))


def _resolver_post(request, autor):
    """Convierte POST en ids resueltos. Retorna `(destinatarios_ids, total_pre_resolucion)`."""
    usuarios_raw = request.POST.getlist("destinatarios_usuarios")
    usuarios_ids: list[int] = []
    for u in usuarios_raw:
        try:
            usuarios_ids.append(int(u))
        except (TypeError, ValueError):
            continue
    grupos = [g for g in request.POST.getlist("destinatarios_grupos") if g]
    dinamicos = [d for d in request.POST.getlist("destinatarios_dinamicos") if d]

    resueltos = services.resolver_destinatarios(
        autor=autor,
        usuarios_ids=usuarios_ids,
        grupos=grupos,
        dinamicos=dinamicos,
    )
    return resueltos


@login_required
@require_http_methods(["GET", "POST"])
def nuevo(request):
    user = request.user
    if not puede(user, "recados", "ver"):
        return _sin_acceso()
    if request.method == "POST" and not puede(user, "recados", "crear"):
        return _sin_acceso()

    form = RecadoForm(request.POST or None)
    grupos = _grupos_disponibles()
    usuarios_qs = Usuario.objects.filter(is_active=True).exclude(pk=user.pk).order_by("nombre_completo")

    if request.method == "POST" and form.is_valid():
        destinatarios = _resolver_post(request, autor=user)
        if not destinatarios:
            messages.error(request, "Debes seleccionar al menos un destinatario válido.")
            return render(request, "recados/form.html", {
                "form": form, "grupos": grupos, "usuarios": usuarios_qs,
                "modo": "nuevo",
                "puede_adjuntar": puede(user, "recados", "adjuntar_drive"),
            })

        confirmado = (request.POST.get("confirmacion_aceptada") or "") in ("1", "true", "on")
        if len(destinatarios) > UMBRAL_CONFIRMACION and not confirmado:
            return JsonResponse(
                {
                    "requiere_confirmacion": True,
                    "total_destinatarios": len(destinatarios),
                },
                status=400,
            )

        cuerpo = sanear_contexto(form.cleaned_data["cuerpo"], max_len=8000)
        recado = services.crear_recado(
            autor=user, cuerpo=cuerpo, destinatarios_ids=destinatarios
        )
        _procesar_adjuntos(request, recado, user)
        messages.success(request, "Recado enviado.")
        return redirect("recados:legacy_detalle", pk=recado.pk)

    return render(request, "recados/form.html", {
        "form": form, "grupos": grupos, "usuarios": usuarios_qs, "modo": "nuevo",
        "puede_adjuntar": puede(user, "recados", "adjuntar_drive"),
    })


# ── Editar ───────────────────────────────────────────────────────────────────


@login_required
@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    user = request.user
    if not puede(user, "recados", "ver"):
        return _sin_acceso()

    recado = get_object_or_404(Recado, pk=pk)
    if recado.autor_id != user.pk:
        return _sin_acceso()
    if not puede(user, "recados", "editar_propios"):
        return _sin_acceso()

    if request.method == "POST":
        cuerpo_actual = recado.cuerpo  # capturar ANTES de form.is_valid (ModelForm muta la instancia)
        form = RecadoForm(request.POST, instance=recado)
        if form.is_valid():
            nuevo_cuerpo = sanear_contexto(form.cleaned_data["cuerpo"], max_len=8000)
            if nuevo_cuerpo and nuevo_cuerpo != cuerpo_actual:
                # Reset al valor original para que editar_recado vea el delta correcto.
                recado.cuerpo = cuerpo_actual
                services.editar_recado(recado=recado, editor=user, nuevo_cuerpo=nuevo_cuerpo)
                messages.success(request, "Recado actualizado.")
            _procesar_adjuntos(request, recado, user)
            return redirect("recados:legacy_detalle", pk=recado.pk)
    else:
        form = RecadoForm(instance=recado)

    return render(request, "recados/form.html", {
        "form": form, "recado": recado, "modo": "editar",
        "grupos": _grupos_disponibles(),
        "usuarios": Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        "puede_adjuntar": puede(user, "recados", "adjuntar_drive"),
    })


# ── Marcar leído ─────────────────────────────────────────────────────────────


@login_required
@require_http_methods(["POST"])
def marcar_leido(request, pk: int):
    user = request.user
    fila = RecadoDestinatario.objects.filter(recado_id=pk, usuario=user).first()
    if fila is None:
        raise Http404
    if fila.leido_en is None:
        fila.leido_en = timezone.now()
        fila.save(update_fields=["leido_en"])
        services.emitir_leido(fila.recado, user)
    return HttpResponse(status=204)


# ── Adjunto: proxy de descarga ───────────────────────────────────────────────


@login_required
@require_http_methods(["GET"])
def adjunto_descargar(request, pk: int):
    """Sirve un adjunto desde Drive al usuario autenticado (sin liga pública).

    Solo quien puede ver el recado puede bajar su adjunto.
    """
    from urllib.parse import quote

    user = request.user
    if not puede(user, "recados", "ver"):
        return _sin_acceso()

    adj = get_object_or_404(RecadoAdjunto.objects.select_related("recado"), pk=pk)
    if not services.puede_ver_recado(user, adj.recado):
        raise Http404("Adjunto no encontrado.")

    from lib.google_drive import drive
    try:
        contenido, mime, nombre = drive.descargar(adj.drive_file_id)
    except Exception:  # noqa: BLE001 — el archivo pudo borrarse en Drive
        raise Http404("No se pudo obtener el archivo de Drive.") from None

    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    disposicion = "inline" if (mime or "").startswith(("image/", "application/pdf")) else "attachment"
    resp["Content-Disposition"] = f"{disposicion}; filename*=UTF-8''{quote(nombre)}"
    return resp


