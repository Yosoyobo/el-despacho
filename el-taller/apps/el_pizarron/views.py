from apps.el_pizarron.forms import ComentarioForm, TareaForm, TareaGlobalForm
from apps.el_pizarron.models import Tarea
from apps.los_proyectos.models import Proyecto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from lib.permisos import (
    es_admin,
    puede_ver_comentario,
    puede_ver_finanzas,
    puede_ver_proyecto,
    puede_ver_tarea,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto


def _comentarios_visibles(user, queryset):
    return [c for c in queryset if puede_ver_comentario(user, c)]


def _sincronizar_menciones_comentario(comentario, autor, contenedor_tipo) -> None:
    """S-Recados-V2: persiste menciones @/#/$ del comentario en la tabla
    Referencia → alimenta el inbox "te taggearon". Best-effort."""
    try:
        from referencias.services import sincronizar_referencias
        sincronizar_referencias(
            texto=comentario.cuerpo, contenedor_tipo=contenedor_tipo,
            contenedor_id=comentario.pk, autor=autor,
        )
    except Exception:  # noqa: BLE001 — una mención rota no debe tumbar el comentario
        pass


@login_required
def lista_tareas(request):
    """Lista global de tareas (S-LC-Feedback-V6): todas las tareas visibles al
    usuario, filtrables por estado / asignación. Antes las tareas sólo se veían
    dentro de cada proyecto y `/pizarron/` no existía (link roto del Dashboard).

    Visibilidad: admins (super_admin/dueño) y contador ven todas; el diseñador
    ve sólo las suyas o las de proyectos donde está asignado.
    """
    from apps.el_pizarron.models.estado_tarea import (
        EstadoTarea,
        slugs_terminales_tarea,
    )
    from django.db.models import Q
    from django.utils import timezone

    user = request.user
    ve_todo = es_admin(user) or puede_ver_finanzas(user)
    visibles = Tarea.objects.select_related("proyecto", "asignada_a", "proyecto__cliente")
    if not ve_todo:
        visibles = visibles.filter(
            Q(asignada_a=user) | Q(responsables=user) | Q(proyecto__asignaciones__usuario=user)
        ).distinct()

    # Estados dinámicos (configurables en Gerencia) — V6 Bloque 1.
    estados = [(e.slug, e.label) for e in EstadoTarea.objects.filter(activo=True)]
    terminales = slugs_terminales_tarea()

    qs = visibles
    estado = (request.GET.get("estado") or "").strip()
    if estado in {s for s, _ in estados}:
        qs = qs.filter(estado=estado)
    elif not estado:
        # Por defecto ocultamos las cerradas (se ven con el filtro explícito).
        qs = qs.exclude(estado__in=terminales)

    # LC #154: el listado oculta las archivadas (las métricas de abajo, que usan
    # `visibles`, sí las siguen contando).
    qs = qs.filter(archivada=False)

    solo_mias = request.GET.get("asignado") == "mio"
    if solo_mias:
        qs = qs.filter(Q(asignada_a=user) | Q(responsables=user)).distinct()

    # Tareas cerradas: orden cronológico por completado, las más recientes
    # arriba (pedido LC 2026-06-29). Las abiertas, por compromiso.
    if estado in terminales:
        qs = qs.order_by("-completada_en", "-creado_en")
    else:
        qs = qs.order_by("fecha_compromiso", "-creado_en")

    hoy = timezone.localdate()
    kpis = {
        "pendientes": visibles.filter(estado="pendiente").count(),
        "en_curso": visibles.filter(estado="en_curso").count(),
        # "Atrasadas" es derivado: compromiso vencido sin estado terminal.
        "atrasadas": visibles.filter(fecha_compromiso__lt=hoy).exclude(estado__in=terminales).count(),
        "mias": visibles.filter(Q(asignada_a=user) | Q(responsables=user)).distinct().exclude(estado__in=terminales).count(),
    }
    return render(request, "pizarron/lista.html", {
        "tareas": list(qs[:300]),
        "estados": estados,
        "estado_filtro": estado,
        "solo_mias": solo_mias,
        "kpis": kpis,
        "ve_todo": ve_todo,
    })


def _tareas_visibles(user):
    from django.db.models import Q
    visibles = Tarea.objects.select_related("proyecto", "asignada_a", "runner", "proyecto__cliente")
    if not (es_admin(user) or puede_ver_finanzas(user)):
        # S-LC-Proyecto-V2: incluye tareas donde el usuario es el runner.
        visibles = visibles.filter(
            Q(asignada_a=user) | Q(responsables=user) | Q(runner=user)
            | Q(proyecto__asignaciones__usuario=user)
        ).distinct()
    return visibles


def _qs_filtros(estados_sel, personas_sel, cat="todas"):
    """Querystring canónico de los filtros combinables del Kanban."""
    partes = ["f=1"]
    partes += [f"estado={s}" for s in sorted(estados_sel)]
    partes += [f"persona={p}" for p in sorted(personas_sel)]
    if cat and cat != "todas":
        partes.append(f"cat={cat}")
    return "?" + "&".join(partes)


@login_required
def kanban_tareas(request):
    """Página Tareas (V6 Bloque 2A): Kanban por estado. Default = mis tareas.
    Filtros de botones siempre visibles y COMBINABLES: estados + personas.
    Estados activos en una fila arriba; terminales (cerradas) en una fila abajo.
    """
    from apps.el_pizarron.mandados import TIPOS_RUNNER
    from apps.el_pizarron.models.estado_tarea import EstadoTarea
    from django.db.models import Q

    from lib.permisos import puede_ser_runner, roles_efectivos

    user = request.user
    visibles = _tareas_visibles(user)

    # LC #154: por default se ocultan las archivadas; «Ver archivadas» las
    # muestra solas (para desarchivar). El contador viene del total visible.
    mostrar_archivadas = request.GET.get("archivadas") == "1"
    archivadas_count = visibles.filter(archivada=True).count()

    estados_def = list(EstadoTarea.objects.filter(activo=True))
    slugs_validos = {e.slug for e in estados_def}

    estados_sel = {s for s in request.GET.getlist("estado") if s in slugs_validos}
    personas_sel = {p for p in request.GET.getlist("persona") if p.isdigit()}
    # Sin interacción previa (sin flag f) → default "mis tareas".
    if "f" not in request.GET and not personas_sel and not estados_sel:
        personas_sel = {str(user.pk)}

    # S-LC-Feedback-V13: filtro de categoría [Todas · General · Mandados].
    cat = (request.GET.get("cat") or "todas").lower()
    if cat not in {"todas", "general", "mandados"}:
        cat = "todas"

    # Runner sin rol amplio: SOLO ve sus mandados (entrega/recoger asignados a él).
    roles = roles_efectivos(user)
    es_runner_only = puede_ser_runner(user) and not (
        roles & {"super_admin", "dueno", "contador", "disenador"}
    )
    if es_runner_only:
        cat = "mandados"
        visibles = visibles.filter(Q(asignada_a=user) | Q(runner=user)).distinct()

    qs = visibles
    if personas_sel and not es_runner_only:
        _pks = [int(p) for p in personas_sel]
        cond = Q(asignada_a__pk__in=_pks) | Q(responsables__pk__in=_pks)
        # S-LC-Proyecto-V2: "mis tareas" también muestra las entregas/recogidas
        # donde soy el runner.
        if str(user.pk) in personas_sel:
            cond |= Q(runner=user)
        qs = qs.filter(cond).distinct()
    if estados_sel:
        qs = qs.filter(estado__in=estados_sel)
    # Categoría: General = no-mandados; Mandados = entrega/recoger.
    if cat == "general":
        qs = qs.exclude(tipo__in=TIPOS_RUNNER)
    elif cat == "mandados":
        qs = qs.filter(tipo__in=TIPOS_RUNNER)
    # LC #154: soft-hide de archivadas (o vista dedicada de archivadas).
    qs = qs.filter(archivada=mostrar_archivadas)

    tareas = list(qs.order_by("fecha_compromiso", "-creado_en")[:500])
    por_estado: dict[str, list] = {}
    for t in tareas:
        por_estado.setdefault(t.estado, []).append(t)

    def _cols(defs):
        return [{
            "slug": e.slug, "label": e.label, "color": e.color,
            "tareas": por_estado.get(e.slug, []),
        } for e in defs]

    cols_activas = _cols([e for e in estados_def if not e.terminal])
    cols_cerradas = _cols([e for e in estados_def if e.terminal])
    # Las columnas cerradas se ordenan por cuándo se marcaron como completadas
    # (más recientes arriba), no por fecha de compromiso (pedido LC 2026-06-29).
    for col in cols_cerradas:
        col["tareas"].sort(
            key=lambda t: t.completada_en or t.creado_en, reverse=True)

    # Chips de filtros: cada uno togglea su valor preservando el resto (incl. cat).
    chips_estado = [{
        "slug": e.slug, "label": e.label, "color": e.color,
        "activo": e.slug in estados_sel,
        "url": _qs_filtros(estados_sel ^ {e.slug}, personas_sel, cat),
    } for e in estados_def]

    from cuentas.models.usuario import Usuario
    chips_persona = [{
        "pk": u.pk,
        "nombre": u.get_short_name() or u.email,
        "activo": str(u.pk) in personas_sel,
        "url": _qs_filtros(estados_sel, personas_sel ^ {str(u.pk)}, cat),
    } for u in Usuario.objects.filter(is_active=True).order_by("nombre_completo")]

    # Pills de categoría (Todas · General · Mandados). Preservan estado/persona.
    cat_pills = [
        {"slug": "todas", "label": "Todas", "activo": cat == "todas",
         "url": _qs_filtros(estados_sel, personas_sel, "todas")},
        {"slug": "general", "label": "General", "activo": cat == "general",
         "url": _qs_filtros(estados_sel, personas_sel, "general")},
        {"slug": "mandados", "label": "🛵 Mandados", "activo": cat == "mandados",
         "url": _qs_filtros(estados_sel, personas_sel, "mandados")},
    ]

    return render(request, "pizarron/kanban.html", {
        "cols_activas": cols_activas,
        "cols_cerradas": cols_cerradas,
        "chips_estado": chips_estado,
        "chips_persona": chips_persona,
        "cat_pills": cat_pills,
        "cat": cat,
        "es_runner_only": es_runner_only,
        "url_limpiar": "?f=1" + ("&cat=" + cat if cat != "todas" else ""),
        "hay_filtros": bool(estados_sel or personas_sel),
        "total": len(tareas),
        # LC #154: toggle «Ver archivadas» + contador.
        "mostrar_archivadas": mostrar_archivadas,
        "archivadas_count": archivadas_count,
        "url_toggle_archivadas": _qs_filtros(estados_sel, personas_sel, cat)
            + ("" if mostrar_archivadas else "&archivadas=1"),
    })


@login_required
def cambiar_estado_tarea(request, pk):
    """Drag & drop del Kanban de tareas: POST con `estado` nuevo (slug de
    EstadoTarea activo). Sincroniza `completada_en` con la terminalidad."""
    from apps.el_pizarron.models.estado_tarea import EstadoTarea

    tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("pizarron-detalle-tarea", pk=pk)
    nuevo = (request.POST.get("estado") or "").strip()
    try:
        estado_def = EstadoTarea.objects.get(slug=nuevo, activo=True)
    except EstadoTarea.DoesNotExist:
        return HttpResponseForbidden("Estado inválido.")
    if tarea.estado == nuevo:
        from django.http import HttpResponse
        return HttpResponse(status=204)
    tarea.estado = nuevo
    if estado_def.terminal and tarea.completada_en is None:
        tarea.completada_en = timezone.now()
    elif not estado_def.terminal:
        tarea.completada_en = None
    tarea.save(update_fields=["estado", "completada_en"])
    if estado_def.terminal:
        emitir(EventoPortavoz(
            tipo="tarea.completada",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"tarea_id": tarea.pk, "proyecto_id": tarea.proyecto_id},
        ))
    from django.http import HttpResponse
    return HttpResponse(status=204)


@login_required
def nueva_tarea_global(request):
    """Form "Nueva Tarea" sin proyecto fijo (V6 Bloque 2B) — accesible desde
    el Dashboard y la página Tareas. Proyecto/persona/tipo con un click."""
    TERMINALES_PRY = {"entregado", "cerrado", "cancelado"}
    if request.method == "POST":
        form = TareaGlobalForm(request.POST)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.creado_por = request.user
            tarea.save()
            from apps.el_pizarron import runners
            runners.aplicar_desde_form(tarea, form.cleaned_data, actor=request.user)
            emitir(EventoPortavoz(
                tipo="tarea.creada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"tarea_id": tarea.pk, "proyecto_id": tarea.proyecto_id, "origen": "form_global"},
            ))
            from apps.taller_home.push_handlers import notificar_tarea_asignada
            notificar_tarea_asignada(tarea, request.user)
            from apps.los_proyectos import servicios_actividad
            servicios_actividad.registrar(
                proyecto=tarea.proyecto, tipo="tarea_creada",
                descripcion=f"Nueva tarea «{tarea.titulo[:60]}»", actor=request.user,
                url=f"/proyectos/{tarea.proyecto_id}/",
            )
            messages.success(request, "Tarea creada.")
            return redirect("tareas-kanban")
    else:
        # Fecha precargada desde el Calendario (?fecha=YYYY-MM-DD). LC 2026-06-29.
        initial = {}
        f = request.GET.get("fecha")
        if f:
            initial["fecha_compromiso"] = f
        form = TareaGlobalForm(initial=initial)
    from cuentas.models.usuario import Usuario
    proyectos_mgr = getattr(Proyecto, "activos", Proyecto.objects)
    proyectos_chips = list(
        proyectos_mgr.exclude(estado__in=TERMINALES_PRY)
        .select_related("cliente").order_by("-creado_en")[:60]
    )
    return render(request, "pizarron/form_tarea_global.html", {
        "form": form,
        "proyectos_chips": proyectos_chips,
        "usuarios_chips": list(Usuario.objects.filter(is_active=True).order_by("nombre_completo")),
        "tipos_chips": Tarea._meta.get_field("tipo").choices,
    })


@login_required
def nueva_tarea(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden()
    if request.method == "POST":
        form = TareaForm(request.POST)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.creado_por = request.user
            tarea.save()
            from apps.el_pizarron import runners
            runners.aplicar_desde_form(tarea, form.cleaned_data, actor=request.user)
            emitir(EventoPortavoz(
                tipo="tarea.creada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"tarea_id": tarea.pk, "proyecto_id": proyecto.pk},
            ))
            from apps.taller_home.push_handlers import notificar_tarea_asignada
            notificar_tarea_asignada(tarea, request.user)
            from apps.los_proyectos import servicios_actividad
            servicios_actividad.registrar(
                proyecto=proyecto, tipo="tarea_creada",
                descripcion=f"Nueva tarea «{tarea.titulo[:60]}»", actor=request.user,
                url=f"/proyectos/{proyecto.pk}/",
            )
            messages.success(request, "Tarea creada.")
            return redirect("pizarron-detalle-tarea", pk=tarea.pk)
    else:
        form = TareaForm()
    return render(request, "pizarron/form_tarea.html", {"form": form, "proyecto": proyecto, "modo": "nueva"})


@login_required
def detalle_tarea(request, pk):
    tarea = get_object_or_404(
        Tarea.objects.select_related("proyecto", "asignada_a").prefetch_related("responsables"),
        pk=pk,
    )
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    comentarios = _comentarios_visibles(
        request.user,
        tarea.comentarios.select_related("autor"),
    )
    puede_ed = puede_ver_proyecto(request.user, tarea.proyecto)
    puede_eliminar = es_admin(request.user) or tarea.creado_por_id == request.user.pk
    responsables = tarea.responsables_todos
    responsables_txt = ", ".join(u.nombre_completo for u in responsables) or "—"
    info_clasificacion = [
        {"label": "Estado", "value": tarea.get_estado_display()},
        {"label": "Tipo", "value": f"{tarea.emoji_tipo} {tarea.get_tipo_display()}"},
        {"label": "Prioridad", "value": tarea.get_prioridad_display()},
        {"label": "Responsables", "value": responsables_txt},
        {"label": "Compromiso", "value": tarea.fecha_compromiso.strftime("%d %b %Y") if tarea.fecha_compromiso else "—"},
    ]
    info_proyecto = [
        {"label": "Código", "value_html": format_html(
            '<a href="{}" class="font-mono text-brand-600 hover:underline dark:text-brand-400">{}</a>',
            reverse("proyectos-detalle", args=[tarea.proyecto.pk]), tarea.proyecto.codigo,
        )},
        {"label": "Cliente", "value": tarea.proyecto.cliente.razon_social if tarea.proyecto.cliente else "—"},
    ]
    action_bar_meta = format_html(
        '<span>{}</span>',
        f"Creada {tarea.creado_en.strftime('%d %b %Y')}" if hasattr(tarea, "creado_en") else "",
    )
    return render(request, "pizarron/detalle_tarea.html", {
        "tarea": tarea,
        "proyecto": tarea.proyecto,
        "comentarios": comentarios,
        "puede_editar": puede_ed,
        "puede_eliminar": puede_eliminar,
        "es_admin": es_admin(request.user),
        "info_clasificacion": info_clasificacion,
        "info_proyecto": info_proyecto,
        "action_bar_meta": action_bar_meta,
        "breadcrumb_items": [
            {"url": reverse("proyectos-lista"), "label": "Proyectos"},
            {"url": reverse("proyectos-detalle", args=[tarea.proyecto.pk]), "label": tarea.proyecto.codigo},
            {"label": tarea.titulo},
        ],
        "back_url": reverse("proyectos-detalle", args=[tarea.proyecto.pk]),
        "back_label": tarea.proyecto.codigo,
    })


@login_required
def eliminar_tarea(request, pk):
    """Elimina PERMANENTEMENTE una tarea (LC 2026-07). Antes solo se archivaba
    (completaba). Gate: admin (super_admin/dueño) o quien la creó. POST puro."""
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=pk)
    if not (es_admin(request.user) or tarea.creado_por_id == request.user.pk):
        return HttpResponseForbidden("Sin permiso para eliminar la tarea.")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    proyecto_pk = tarea.proyecto_id
    titulo = tarea.titulo
    tarea.delete()
    emitir(EventoPortavoz(
        tipo="tarea.eliminada",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"titulo": titulo[:120], "proyecto_id": proyecto_pk},
    ))
    messages.success(request, f"Tarea «{titulo[:60]}» eliminada.")
    destino = request.POST.get("next") or reverse("proyectos-detalle", args=[proyecto_pk])
    return redirect(destino)


@login_required
def archivar_tarea(request, pk):
    """LC #154: archiva/desarchiva una tarea (soft-hide reversible). NO borra —
    sigue en métricas. POST puro. Cualquiera que pueda ver la tarea la archiva."""
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    tarea.archivada = not tarea.archivada
    tarea.save(update_fields=["archivada"])
    emitir(EventoPortavoz(
        tipo="tarea.archivada",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"tarea_id": tarea.pk, "archivada": tarea.archivada,
                 "proyecto_id": tarea.proyecto_id},
    ))
    messages.success(
        request,
        f"Tarea «{tarea.titulo[:60]}» {'archivada' if tarea.archivada else 'desarchivada'}.")
    destino = request.POST.get("next") or reverse("tareas-kanban")
    return redirect(destino)


@login_required
def editar_tarea(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method == "POST":
        form = TareaForm(request.POST, instance=tarea)
        if form.is_valid():
            form.save()
            from apps.el_pizarron import runners
            runners.aplicar_desde_form(tarea, form.cleaned_data, actor=request.user)
            messages.success(request, "Tarea actualizada.")
            return redirect("pizarron-detalle-tarea", pk=tarea.pk)
    else:
        form = TareaForm(instance=tarea)
    return render(request, "pizarron/form_tarea.html", {"form": form, "tarea": tarea, "proyecto": tarea.proyecto, "modo": "editar"})


@login_required
def editar_tarea_rapido(request, pk):
    """D6 (LC 2026-07): modal CORTO de edición de tarea (desde el calendario).
    GET HTMX → modal compacto; POST → guarda campos clave y refresca (HX-Redirect).
    Sin comentarios. Fallback no-HTMX al detalle completo."""
    from .forms import TareaRapidaForm
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = TareaRapidaForm(request.POST, instance=tarea)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="tarea.creada", actor_id=request.user.pk, actor_email=request.user.email,
                payload={"tarea_id": tarea.pk, "proyecto_id": tarea.proyecto_id, "editada_rapido": True},
            ))
            destino = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("calendario-index")
            if es_htmx:
                from django.http import HttpResponse
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
        return render(request, "pizarron/_modal_tarea_rapida.html",
                      {"form": form, "tarea": tarea, "next": request.POST.get("next", "")})
    form = TareaRapidaForm(instance=tarea)
    return render(request, "pizarron/_modal_tarea_rapida.html",
                  {"form": form, "tarea": tarea, "next": request.GET.get("next", "")})


@login_required
def completar_tarea(request, pk):
    if request.method != "POST":
        return redirect("pizarron-detalle-tarea", pk=pk)
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    tarea.estado = "completada"
    tarea.completada_en = timezone.now()
    tarea.save(update_fields=["estado", "completada_en"])
    emitir(EventoPortavoz(
        tipo="tarea.completada",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"tarea_id": tarea.pk, "proyecto_id": tarea.proyecto_id},
    ))
    messages.success(request, "Tarea completada.")
    return redirect("pizarron-detalle-tarea", pk=tarea.pk)


@login_required
def comentar_tarea(request, pk):
    tarea = get_object_or_404(Tarea, pk=pk)
    if not puede_ver_tarea(request.user, tarea):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("pizarron-detalle-tarea", pk=pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.tarea = tarea
        c.autor = request.user
        c.cuerpo = sanear_contexto(c.cuerpo)
        # Diseñadores no pueden marcar comentarios como internos (privilegio admin/contador).
        if not es_admin(request.user) and getattr(request.user, "rol", None) != "contador":
            c.es_interno = False
        c.save()
        _sincronizar_menciones_comentario(c, request.user, "comentario_tarea")
        if tarea.proyecto_id:
            from apps.los_proyectos import servicios_actividad
            servicios_actividad.registrar(
                proyecto=tarea.proyecto, tipo="comentario",
                descripcion=f"Comentario en tarea «{tarea.titulo[:60]}»", actor=request.user,
                url=f"/proyectos/{tarea.proyecto_id}/",
            )
        messages.success(request, "Comentario agregado.")
    else:
        messages.error(request, "Comentario inválido.")
    return redirect("pizarron-detalle-tarea", pk=tarea.pk)


@login_required
def comentar_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("proyectos-detalle", pk=proyecto.pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.proyecto = proyecto
        c.autor = request.user
        c.cuerpo = sanear_contexto(c.cuerpo)
        if not es_admin(request.user) and getattr(request.user, "rol", None) != "contador":
            c.es_interno = False
        c.save()
        _sincronizar_menciones_comentario(c, request.user, "comentario_proyecto")
        from apps.los_proyectos import servicios_actividad
        servicios_actividad.registrar(
            proyecto=proyecto, tipo="comentario",
            descripcion="Comentario en el proyecto", actor=request.user,
            url=f"/proyectos/{proyecto.pk}/",
        )
        messages.success(request, "Comentario agregado al proyecto.")
    return redirect("proyectos-detalle", pk=proyecto.pk)


# ── El Runner — Mandados (S-Chalan-Barrido parte 2) ───────────────────────────

def _mandado_visible_o_404(request, pk):
    from apps.el_pizarron.mandados import mandados_visibles
    m = mandados_visibles(request.user).filter(pk=pk).first()
    if m is None:
        from django.http import Http404
        raise Http404("Mandado no encontrado o sin acceso.")
    return m


@login_required
def mandados_lista(request):
    """Lista propia de El Runner: entregas/recolecciones como entidad logística,
    filtrables por estado de reparto. Cada fila enlaza a su proyecto y permite
    avanzar el estado o fijar el destino (pin)."""
    from apps.el_pizarron.mandados import mandados_visibles
    from apps.el_pizarron.models.mandado import ESTADOS_MANDADO

    qs = mandados_visibles(request.user)
    estados_validos = {s for s, _, _ in ESTADOS_MANDADO}
    estado_sel = request.GET.get("estado", "")
    if estado_sel in estados_validos:
        qs = qs.filter(estado=estado_sel)

    mandados = list(qs.order_by("estado", "tarea__fecha_compromiso", "-creado_en")[:300])

    base = reverse("mandados-lista")
    chips = [{
        "slug": "", "label": "Todos",
        "url": base, "activo": estado_sel == "",
    }]
    for slug, label, color in ESTADOS_MANDADO:
        chips.append({
            "slug": slug, "label": label, "color": color,
            "url": f"{base}?estado={slug}", "activo": estado_sel == slug,
        })

    return render(request, "mandados/lista.html", {
        "mandados": mandados,
        "chips": chips,
        "total": len(mandados),
        "puede_admin": es_admin(request.user),
    })


@login_required
def mandado_avanzar(request, pk):
    """POST: avanza el estado de reparto (en_camino | entregado | cancelar)."""
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    from apps.el_pizarron import mandados as svc
    m = _mandado_visible_o_404(request, pk)
    accion = (request.POST.get("accion") or "").strip()
    evento = None
    try:
        if accion == "en_camino":
            svc.marcar_en_camino(m)
            evento = "en_camino"
            messages.success(request, "Mandado marcado en camino.")
        elif accion == "entregado":
            svc.marcar_entregado(m)
            evento = "entregado"
            messages.success(request, "Mandado entregado. ✅")
        elif accion == "cancelar":
            svc.cancelar(m, motivo=(request.POST.get("motivo") or "").strip())
            evento = "cancelado"
            messages.success(request, "Mandado cancelado.")
        else:
            messages.error(request, "Acción no válida.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if evento:
        # Push a los involucrados (quien lo mandó, asignado, runner) — A8.
        svc.notificar_involucrados(m, evento, actor=request.user)
        _emitir_mandado("mandado.estado_cambiado", request.user, m, {"accion": accion})
    return redirect("mandados-lista")


@login_required
def mandado_destino(request, pk):
    """Fija el destino (pin Leaflet). GET (HTMX) → modal con mapa; POST → guarda
    lat/lng/etiqueta en la Tarea subyacente."""
    from apps.el_pizarron import mandados as svc
    m = _mandado_visible_o_404(request, pk)

    if request.method == "POST":
        try:
            lat = float(request.POST.get("lat"))
            lng = float(request.POST.get("lng"))
        except (TypeError, ValueError):
            messages.error(request, "Coordenadas inválidas.")
            return redirect("mandados-lista")
        svc.fijar_destino(m, lat=lat, lng=lng, etiqueta=(request.POST.get("etiqueta") or "").strip())
        _emitir_mandado("mandado.destino_fijado", request.user, m, {"lat": lat, "lng": lng})
        if request.headers.get("HX-Request") == "true":
            from django.http import HttpResponse
            return HttpResponse(status=204, headers={"HX-Redirect": reverse("mandados-lista")})
        messages.success(request, "Destino del mandado actualizado.")
        return redirect("mandados-lista")

    # Los POIs ya no se precargan: el geo-picker los trae en vivo desde
    # /geo/buscar conforme el usuario escribe (cuadro de resultados).
    return render(request, "mandados/_modal_destino.html", {"m": m})


@login_required
def geocoding_buscar(request):
    """Proxy server-side a Nominatim (OSM) + POIs internos. Reusado por el
    geo-picker (cuadro de resultados en vivo), el modal de destino y El Chalán.

    - `?q=` → `{pois: [...], resultados: [...]}` (lugares conocidos + direcciones).
      Pasa `&pois=0` para omitir los POIs (modo "solo direcciones", p. ej. el
      autocompletado de la dirección de un cliente/proveedor).
    - `?lat=&lng=` → `{punto: {...}}` (identifica el punto al picar el mapa).
    """
    from django.http import JsonResponse
    lat, lng = request.GET.get("lat"), request.GET.get("lng")
    if lat and lng:
        from lib.geocoding import identificar
        return JsonResponse({"punto": identificar(lat, lng)})
    from lib.geocoding import buscar
    q = request.GET.get("q", "")
    # LC 2026-07 (D4): modo ACOTADO — para mandados/tareas el buscador se limita
    # a direcciones GUARDADAS (clientes/proveedores) + POIs internos, SIN abrir la
    # API del mapa mundial. El mapa (Nominatim) solo entra con `&mapa=1` ("mapa
    # opcional", decisión Oscar Q2).
    acotado = request.GET.get("acotado") == "1"
    con_mapa = request.GET.get("mapa") == "1"
    pois: list[dict] = []
    if request.GET.get("pois") != "0":
        from apps.el_pizarron.poi import buscar_pois
        pois = buscar_pois(q)
    if acotado:
        pois = _direcciones_guardadas(q) + pois
        resultados = buscar(q) if con_mapa else []
    else:
        resultados = buscar(q)
    return JsonResponse({"pois": pois, "resultados": resultados})


def _direcciones_guardadas(q: str, limite: int = 8) -> list[dict]:
    """Direcciones GUARDADAS de clientes/proveedores que matchean `q` (razón
    social o dirección/fiscal). Formato POI: {label, direccion, lat, lng, fuente}.
    Sin visita geolocalizada: usa la dirección fiscal (o la normal) como texto."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente
    from django.db.models import Q as _Q
    filtro = _Q(razon_social__icontains=q) | _Q(direccion__icontains=q) | _Q(direccion_fiscal__icontains=q)
    out: list[dict] = []
    for c in Cliente.activos.filter(filtro)[:limite]:
        d = (c.direccion_fiscal or c.direccion or "").strip()
        out.append({"label": c.razon_social, "direccion": d or c.razon_social,
                    "lat": c.lat, "lng": c.lng, "fuente": "cliente"})
    for p in Proveedor.objects.filter(filtro, activo=True)[:limite]:
        d = (p.direccion_fiscal or p.direccion or "").strip()
        out.append({"label": p.razon_social, "direccion": d or p.razon_social,
                    "lat": p.lat, "lng": p.lng, "fuente": "proveedor"})
    return out[:limite]


def _emitir_mandado(tipo, usuario, mandado, extra=None):
    import contextlib
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(
            tipo=tipo,  # type: ignore[arg-type]
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload={"mandado_id": mandado.pk, "tarea_id": mandado.tarea_id, **(extra or {})},
        ))
