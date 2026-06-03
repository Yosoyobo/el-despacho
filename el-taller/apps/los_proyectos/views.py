import contextlib

from apps.la_cartera.models import Cliente
from apps.los_proyectos.forms import (
    AsignacionForm,
    CambiarEstadoForm,
    EditarEconomicoForm,
    EditarFechasForm,
    ProyectoForm,
    ProyectoProductoForm,
    ProyectoProductoFormSet,
    ProyectoProductoFormSetEdit,
)
from apps.los_proyectos.models import (
    ESTADOS_PROYECTO,
    EstadoProyecto,
    Proyecto,
    ProyectoAsignacion,
    ProyectoProducto,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.los_proyectos.templatetags.proyectos_extras import dentro_de

from lib.permisos import (
    es_admin,
    puede_editar_proyecto,
    puede_ver_proyecto,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _servicios_datos_json():
    """Mapa {servicio_id: {precio, costo}} para que el form de Proyecto
    pre-llene precio/costo al elegir un producto (C4 S-LC-Feedback-V6)."""
    import json

    from apps.el_catalogo.models import Servicio
    datos = {
        str(s.pk): {"precio": str(s.precio_base or 0), "costo": str(s.costo or 0)}
        for s in Servicio.objects.filter(activo=True).only("pk", "precio_base", "costo")
    }
    return json.dumps(datos)


def _fmt_fechahora(dt):
    """Formatea un datetime aware como 'dd Mmm YYYY · HH:MM' en hora local."""
    if not dt:
        return "—"
    return timezone.localtime(dt).strftime("%d %b %Y · %H:%M")


def _proyectos_visibles(user):
    """Queryset filtrado por rol."""
    rol = getattr(user, "rol", None)
    qs = Proyecto.objects.select_related("cliente")
    if rol in ("super_admin", "dueno", "contador"):
        return qs
    if rol == "disenador":
        return qs.filter(asignaciones__usuario=user).distinct()
    return Proyecto.objects.none()


@login_required
def lista(request):
    q = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado") or ""
    kpi_activo = (request.GET.get("kpi") or "").strip()
    # Mapeo KPI → conjunto de estados a filtrar (KPI hero clickeable).
    KPI_MAP = {
        "prospectos": ("por_cotizar",),
        "activos": ("en_proceso_diseno", "en_proceso_produccion"),
        "pausa": ("en_pausa",),
        "entregados": ("entregado",),
    }
    qs = _proyectos_visibles(request.user)
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(cliente__razon_social__icontains=q))
    if estado:
        qs = qs.filter(estado=estado)
    elif kpi_activo in KPI_MAP:
        qs = qs.filter(estado__in=KPI_MAP[kpi_activo])
    orden_permitido = {"codigo", "nombre", "estado", "fecha_compromiso", "creado_en"}
    orden = (request.GET.get("orden") or "-creado_en").strip()
    if orden.lstrip("-") not in orden_permitido:
        orden = "-creado_en"
    qs = qs.order_by(orden, "pk").prefetch_related("productos__servicio", "productos__variacion")
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    base = _proyectos_visibles(request.user)
    kpis = {
        "prospectos": base.filter(estado="por_cotizar").count(),
        "activos": base.filter(estado__in=("en_proceso_diseno", "en_proceso_produccion")).count(),
        "pausa": base.filter(estado="en_pausa").count(),
        "entregados": base.filter(estado="entregado").count(),
    }
    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if estado:
        qs_filtros.append(f"estado={estado}")
    if kpi_activo in KPI_MAP and not estado:
        qs_filtros.append(f"kpi={kpi_activo}")
    querystring_base = "&".join(qs_filtros)

    def _kpi_link(slug):
        if kpi_activo == slug and not estado:
            return "?"  # toggle off
        parts = []
        if q:
            parts.append(f"q={q}")
        parts.append(f"kpi={slug}")
        return "?" + "&".join(parts)
    return render(request, "proyectos/lista.html", {
        "proyectos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "estado": estado,
        "estados_disponibles": ESTADOS_PROYECTO,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_filtros + ([f"orden={orden}"] if orden != "-creado_en" else [])),
        "cabeceras_proyectos": [
            # S-LC-Feedback-V4: nombre es lo principal, código secundario.
            {"label": "Proyecto", "sort_key": "nombre"},
            {"label": "Cliente"},
            {"label": "Estado", "sort_key": "estado"},
            {"label": "Compromiso", "sort_key": "fecha_compromiso"},
        ],
        "puede_crear": puede_editar_proyecto(request.user, None),
        "es_admin": es_admin(request.user),
        "kpis": kpis,
        "kpi_links": {
            "prospectos": _kpi_link("prospectos"),
            "activos": _kpi_link("activos"),
            "pausa": _kpi_link("pausa"),
            "entregados": _kpi_link("entregados"),
        },
        "kpi_activos": {
            "prospectos": kpi_activo == "prospectos" and not estado,
            "activos": kpi_activo == "activos" and not estado,
            "pausa": kpi_activo == "pausa" and not estado,
            "entregados": kpi_activo == "entregados" and not estado,
        },
    })


@login_required
@ensure_csrf_cookie
def kanban(request):
    """Vista Kanban: columnas por estado, tarjetas movibles visualmente.

    `ensure_csrf_cookie` garantiza que la cookie `csrftoken` exista al cargar
    la página — el drag-and-drop hace POST a /cambiar-estado/ leyendo el token
    de esa cookie (no hay <form> visible que lo siembre). Sin esto, el POST
    salía con token vacío → 403 → "No se pudo cambiar el estado".
    """
    qs = _proyectos_visibles(request.user).prefetch_related(
        "productos__servicio", "productos__variacion",
    )
    # C3 S-LC-Feedback-V6: dos filas. Arriba el flujo activo; abajo los
    # estados de cierre/pausa. Estados custom nuevos caen arriba por default.
    SLUGS_FILA_ABAJO = ("entregado", "en_pausa", "cancelado")
    columnas = {}
    for slug, label in ESTADOS_PROYECTO:
        proyectos = list(qs.filter(estado=slug).order_by("fecha_compromiso", "-creado_en"))
        columnas[slug] = {"slug": slug, "label": label, "proyectos": proyectos, "total": len(proyectos)}
    fila_arriba = [columnas[s] for s, _ in ESTADOS_PROYECTO if s not in SLUGS_FILA_ABAJO]
    fila_abajo = [columnas[s] for s in SLUGS_FILA_ABAJO if s in columnas]
    return render(request, "proyectos/kanban.html", {
        "fila_arriba": fila_arriba,
        "fila_abajo": fila_abajo,
        "puede_crear": puede_editar_proyecto(request.user, None),
    })


@login_required
def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    puede_ed = puede_editar_proyecto(request.user, proyecto)
    acciones_proyecto = []
    if puede_ed:
        acciones_proyecto = [
            {"url": f"/proyectos/{proyecto.pk}/editar/", "label": "Editar datos"},
            {"url": f"/proyectos/{proyecto.pk}/cambiar-estado/", "label": "Cambiar estado"},
        ]
    asignaciones = list(proyecto.asignaciones.select_related("usuario"))
    estados_disponibles = list(
        EstadoProyecto.objects.filter(activo=True).order_by("orden").values("slug", "label")
    )
    # Proveedores aplicables: derivados de los productos del proyecto vía
    # M2M Servicio.proveedores (S-LC-Feedback-V3).
    from apps.el_catalogo.models import Proveedor
    proveedores_aplicables = list(
        Proveedor.objects.filter(
            activo=True,
            servicios__en_proyectos__proyecto=proyecto,
        ).distinct().order_by("razon_social")
    )
    info_fechas = [
        {"label": "Inicio", "value": _fmt_fechahora(proyecto.fecha_inicio)},
        {"label": "Entrega", "value": (
            f"{_fmt_fechahora(proyecto.fecha_compromiso)} ({dentro_de(proyecto.fecha_compromiso)})"
            if proyecto.fecha_compromiso else "—"
        )},
    ]
    info_economico = [
        {"label": "Monto estimado", "value": f"$ {proyecto.monto_estimado}" if proyecto.monto_estimado else "—"},
        {"label": "Cliente", "value_html": format_html(
            '<a href="{}" class="text-brand-600 hover:underline dark:text-brand-400">{}</a>',
            reverse("cartera-detalle", args=[proyecto.cliente.pk]), proyecto.cliente.razon_social,
        )},
    ]
    if asignaciones:
        equipo_html = format_html_join(
            "",
            '<li class="flex items-center justify-between gap-3"><span class="text-gray-900 dark:text-gray-100">{}</span><span class="badge badge-brand">{}</span></li>',
            ((a.usuario.nombre_completo or a.usuario.email, a.get_rol_en_proyecto_display()) for a in asignaciones),
        )
        info_equipo_html = format_html('<ul class="space-y-1.5">{}</ul>', equipo_html)
    else:
        info_equipo_html = mark_safe('<span class="text-gray-500 dark:text-gray-400">Sin asignar.</span>')
    action_bar_meta = format_html(
        '<span>Última actualización <time class="text-gray-700 dark:text-gray-200">{}</time></span>',
        proyecto.actualizado_en.strftime("%d %b %Y %H:%M"),
    )
    if puede_ed:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">Editar</a>'
            '<a href="{}" class="btn-primario">Asignar</a>',
            reverse("proyectos-editar", args=[proyecto.pk]),
            reverse("proyectos-asignar", args=[proyecto.pk]),
        )
    else:
        action_bar_acciones = ""
    return render(request, "proyectos/detalle.html", {
        "proyecto": proyecto,
        "asignaciones": asignaciones,
        "estados_disponibles": estados_disponibles,
        "proveedores_aplicables": proveedores_aplicables,
        "productos": proyecto.productos.select_related("servicio", "variacion").all(),
        "tareas": proyecto.tareas.select_related("asignada_a").order_by("estado", "-creado_en"),
        "puede_editar": puede_ed,
        "acciones_proyecto": acciones_proyecto,
        "info_fechas": info_fechas,
        "info_economico": info_economico,
        "info_equipo_html": info_equipo_html,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "breadcrumb_items": [
            {"url": reverse("proyectos-lista"), "label": "Proyectos"},
            {"label": proyecto.codigo},
        ],
        "back_url": reverse("proyectos-lista"),
        "back_label": "Proyectos",
    })


@login_required
def nuevo(request):
    if not puede_editar_proyecto(request.user, None):
        return HttpResponseForbidden("Solo admins pueden crear proyectos.")
    if request.method == "POST":
        form = ProyectoForm(request.POST)
        formset = ProyectoProductoFormSet(request.POST, instance=Proyecto())
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.creado_por = request.user
            proyecto.save()
            formset = ProyectoProductoFormSet(request.POST, instance=proyecto)
            if formset.is_valid():
                formset.save()
                proyecto.recalcular_monto_estimado()  # C4: estimado = Σ subtotales
            emitir(EventoPortavoz(
                tipo="proyecto.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo, "cliente_id": proyecto.cliente_id, "estado": proyecto.estado},
            ))
            from apps.taller_home.push_handlers import notificar_proyecto_creado
            notificar_proyecto_creado(proyecto, request.user)
            messages.success(request, f"Proyecto {proyecto.codigo} creado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = ProyectoForm()
        formset = ProyectoProductoFormSet(instance=Proyecto())
    from apps.el_catalogo.models import CategoriaServicio
    return render(request, "proyectos/form.html", {
        "form": form, "formset": formset, "modo": "nuevo",
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "servicios_datos_json": _servicios_datos_json(),
    })


@login_required
def editar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins pueden editar proyectos.")
    if request.method == "POST":
        form = ProyectoForm(request.POST, instance=proyecto)
        formset = ProyectoProductoFormSetEdit(request.POST, instance=proyecto)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            proyecto.recalcular_monto_estimado()  # C4: estimado = Σ subtotales
            messages.success(request, "Proyecto actualizado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto)
        formset = ProyectoProductoFormSetEdit(instance=proyecto)
    from apps.el_catalogo.models import CategoriaServicio
    return render(request, "proyectos/form.html", {
        "form": form, "formset": formset, "modo": "editar", "proyecto": proyecto,
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "servicios_datos_json": _servicios_datos_json(),
    })


@login_required
def cliente_inline(request):
    """Modal HTMX para crear un Cliente nuevo desde el form de Proyecto.

    GET HTMX  → renderiza modal con form.
    POST HTMX éxito → 200 con OOB swap del <select cliente> incluyendo
                       el nuevo cliente seleccionado + cierre del modal.
    POST HTMX falla → reinyecta modal con errores.
    """
    from apps.los_proyectos.forms import ClienteInlineForm

    if not puede_editar_proyecto(request.user, None):
        return HttpResponseForbidden()
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = ClienteInlineForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            emitir(EventoPortavoz(
                tipo="cliente.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"cliente_id": cliente.pk, "origen": "form_proyecto"},
            ))
            if es_htmx:
                return render(request, "proyectos/_cliente_select_oob.html", {
                    "clientes": Cliente.activos.all(), "seleccionado": cliente.pk,
                })
            return redirect("cartera-detalle", pk=cliente.pk)
    else:
        form = ClienteInlineForm()
    return render(request, "proyectos/_modal_cliente.html", {"form": form})


@login_required
def cambiar_estado(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins cambian estado.")
    es_htmx = request.headers.get("HX-Request") == "true"
    # S-Proyecto-Estados-V1: si llega `estado` directo en POST sin
    # `fecha_real_entrega`, lo tratamos como dropdown inline y devolvemos
    # el badge actualizado por OOB. El modal sigue funcionando para
    # fallback no-HTMX.
    inline = request.method == "POST" and "fecha_real_entrega" not in request.POST
    if request.method == "POST":
        if inline:
            form = CambiarEstadoForm({"estado": request.POST.get("estado", "")})
        else:
            form = CambiarEstadoForm(request.POST)
        if form.is_valid():
            anterior = proyecto.estado
            nuevo = form.cleaned_data["estado"]
            proyecto.estado = nuevo
            updates = ["estado", "actualizado_en"]
            if nuevo == "entregado" and form.cleaned_data.get("fecha_real_entrega"):
                proyecto.fecha_real_entrega = form.cleaned_data["fecha_real_entrega"]
                updates.append("fecha_real_entrega")
            proyecto.save(update_fields=updates)
            emitir(EventoPortavoz(
                tipo="proyecto.status_cambiado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "anterior": anterior, "nuevo": nuevo},
            ))
            from apps.taller_home.push_handlers import notificar_proyecto_status_cambiado
            notificar_proyecto_status_cambiado(proyecto, anterior, nuevo, request.user)
            if inline and es_htmx:
                # Devolvemos solo el partial del badge para swap inline.
                return render(request, "proyectos/_badge_estado.html", {
                    "proyecto": proyecto,
                    "estados_disponibles": list(
                        EstadoProyecto.objects.filter(activo=True).order_by("orden").values("slug", "label")
                    ),
                    "puede_editar": True,
                })
            messages.success(request, f"Estado: {anterior} → {nuevo}")
            destino = reverse("proyectos-detalle", args=[proyecto.pk])
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
    else:
        form = CambiarEstadoForm(initial={"estado": proyecto.estado})
    template = "proyectos/_modal_cambiar_estado.html" if es_htmx else "proyectos/cambiar_estado.html"
    return render(request, template, {"form": form, "proyecto": proyecto})


@login_required
def asignar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Solo admins asignan.")
    if request.method == "POST":
        accion = request.POST.get("accion", "agregar")
        if accion == "quitar":
            ProyectoAsignacion.objects.filter(proyecto=proyecto, pk=request.POST.get("asignacion_id") or 0).delete()
            messages.success(request, "Asignación removida.")
            return redirect("proyectos-asignar", pk=proyecto.pk)
        form = AsignacionForm(request.POST)
        if form.is_valid():
            asig = form.save(commit=False)
            asig.proyecto = proyecto
            try:
                asig.save()
                messages.success(request, f"Asignado {asig.usuario.nombre_completo}.")
            except Exception as exc:
                messages.error(request, f"No se pudo asignar: {exc}")
            return redirect("proyectos-asignar", pk=proyecto.pk)
    else:
        form = AsignacionForm()
    return render(request, "proyectos/asignar.html", {
        "form": form,
        "proyecto": proyecto,
        "asignaciones": proyecto.asignaciones.select_related("usuario"),
    })


# ── S-LC-Feedback-V5 c4: quick-edits inline ────────────────────────────


def _es_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _redir_detalle(proyecto):
    return reverse("proyectos-detalle", args=[proyecto.pk])


@login_required
def editar_fechas(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = EditarFechasForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "campo": "fechas"},
            ))
            messages.success(request, "Fechas actualizadas.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": _redir_detalle(proyecto)})
            return redirect(_redir_detalle(proyecto))
    else:
        form = EditarFechasForm(instance=proyecto)
    return render(request, "proyectos/_modal_editar_fechas.html", {"form": form, "proyecto": proyecto})


@login_required
def editar_economico(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = EditarEconomicoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proyecto.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "campo": "economico"},
            ))
            messages.success(request, "Datos económicos actualizados.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": _redir_detalle(proyecto)})
            return redirect(_redir_detalle(proyecto))
    else:
        form = EditarEconomicoForm(instance=proyecto)
    return render(request, "proyectos/_modal_editar_economico.html", {"form": form, "proyecto": proyecto})


@login_required
def agregar_tarea_modal(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    from apps.el_pizarron.forms import TareaForm
    from apps.taller_home.push_handlers import notificar_tarea_asignada
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = TareaForm(request.POST)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.creada_por = request.user
            tarea.save()
            emitir(EventoPortavoz(
                tipo="tarea.creada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"tarea_id": tarea.pk, "proyecto_id": proyecto.pk},
            ))
            with contextlib.suppress(Exception):
                notificar_tarea_asignada(tarea, request.user)
            messages.success(request, f"Tarea «{tarea.titulo}» creada.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": _redir_detalle(proyecto)})
            return redirect(_redir_detalle(proyecto))
    else:
        form = TareaForm()
    return render(request, "proyectos/_modal_agregar_tarea.html", {"form": form, "proyecto": proyecto})


@login_required
def agregar_producto_modal(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = ProyectoProductoForm(request.POST)
        if form.is_valid():
            prod = form.save(commit=False)
            prod.proyecto = proyecto
            prod.save()
            proyecto.recalcular_monto_estimado()  # C4
            emitir(EventoPortavoz(
                tipo="proyecto.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "campo": "producto_agregado", "producto_id": prod.pk},
            ))
            messages.success(request, "Producto agregado.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": _redir_detalle(proyecto)})
            return redirect(_redir_detalle(proyecto))
    else:
        form = ProyectoProductoForm()
    return render(request, "proyectos/_modal_agregar_producto.html", {"form": form, "proyecto": proyecto})


@login_required
def quitar_producto(request, pk, prod_pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    ProyectoProducto.objects.filter(proyecto=proyecto, pk=prod_pk).delete()
    proyecto.recalcular_monto_estimado()  # C4
    messages.success(request, "Producto quitado.")
    return redirect(_redir_detalle(proyecto))
