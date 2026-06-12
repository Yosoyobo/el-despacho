import contextlib
from decimal import Decimal

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
    ROLES_PROYECTO,
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
from django.views.decorators.csrf import ensure_csrf_cookie

from lib.permisos import (
    es_admin,
    puede_editar_proyecto,
    puede_ver_proyecto,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _servicios_datos_json():
    """Mapa {servicio_id: {precio, costo, categoria}} para que el form de
    Proyecto pre-llene precio/costo al elegir un producto y filtre el
    selector de Producto por Categoría (Render-V1)."""
    import json

    from apps.el_catalogo.models import Servicio
    datos = {
        str(s.pk): {
            "precio": str(s.precio_base or 0),
            "costo": str(s.costo or 0),
            "categoria": str(s.categoria_id or ""),
        }
        for s in Servicio.objects.filter(activo=True).only("pk", "precio_base", "costo", "categoria_id")
    }
    return json.dumps(datos)


def _proveedores_activos():
    """Proveedores activos para los selects (principal + impresión)."""
    from apps.el_catalogo.models import Proveedor
    return list(Proveedor.objects.filter(activo=True).order_by("razon_social"))


def _proveedores_panel(proyecto):
    """Deuda por proveedor (auto-sumada de los productos) fusionada con la
    asignación explícita (tipo entregan/recogemos, compromiso, contacto)."""
    asignados = {
        pv.proveedor_id: pv
        for pv in proyecto.proveedores_asignados.select_related("proveedor").all()
    }
    filas, vistos = [], set()
    for d in proyecto.deuda_por_proveedor():
        pid = d["proveedor"].pk
        vistos.add(pid)
        filas.append({"proveedor": d["proveedor"], "total": d["total"], "asignacion": asignados.get(pid)})
    for pid, pv in asignados.items():
        if pid not in vistos:
            filas.append({"proveedor": pv.proveedor, "total": Decimal("0.00"), "asignacion": pv})
    return filas


def _anotar_procesos(formset):
    """Para render (GET): anota en cada form su proceso de impresión y la lista
    de procesos operativos, para prellenar la tarjeta."""
    for form in formset.forms:
        inst = getattr(form, "instance", None)
        impresion, operativos = None, []
        if inst and inst.pk:
            for p in inst.procesos.all().order_by("orden", "creado_en"):
                if p.tipo == "impresion" and impresion is None:
                    impresion = p
                elif p.tipo == "operativo":
                    operativos.append(p)
        form.proc_impresion = impresion
        form.procs_operativos = operativos


def _sync_procesos_formset(formset):
    """Tras formset.save(): sincroniza los procesos (impresión + operativos)
    de cada línea que sobrevivió (no borrada, con pk)."""
    from .services_procesos import sincronizar_procesos
    borrados = set(formset.deleted_forms)
    for form in formset.forms:
        if form in borrados:
            continue
        inst = getattr(form, "instance", None)
        if not inst or not inst.pk:
            continue
        sincronizar_procesos(inst, form.cleaned_data.get("procesos_json"))


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
    SLUGS_FILA_ABAJO = ("entregado", "cerrado", "en_pausa", "cancelado")
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


def _reconciliar_equipo(request, proyecto):
    """C7 S-LC-Feedback-V6: ajusta el equipo según los checkboxes `equipo_<id>`
    y los selects `rol_<id>`. Marcado = asignado (crea/actualiza rol);
    desmarcado = se quita del proyecto."""
    from cuentas.models.usuario import Usuario
    roles_validos = dict(ROLES_PROYECTO)
    actuales = {a.usuario_id: a for a in proyecto.asignaciones.all()}
    for u in Usuario.objects.filter(is_active=True):
        marcado = request.POST.get(f"equipo_{u.pk}") in ("on", "1", "true")
        rol = request.POST.get(f"rol_{u.pk}") or "disenador"
        if rol not in roles_validos:
            rol = "disenador"
        if marcado:
            a = actuales.get(u.pk)
            if a is None:
                ProyectoAsignacion.objects.create(proyecto=proyecto, usuario=u, rol_en_proyecto=rol)
            elif a.rol_en_proyecto != rol:
                a.rol_en_proyecto = rol
                a.save(update_fields=["rol_en_proyecto"])
        elif u.pk in actuales:
            actuales[u.pk].delete()


def _comentarios_proyecto_visibles(user, proyecto):
    """Comentarios del proyecto filtrados por visibilidad (es_interno)."""
    from lib.permisos import puede_ver_comentario
    qs = proyecto.comentarios.select_related("autor").order_by("creado_en")
    return [c for c in qs if puede_ver_comentario(user, c)]


def _ctx_equipo(proyecto):
    """Lista de todos los usuarios activos con su estado asignado/rol para el
    widget de equipo del detalle."""
    from cuentas.models.usuario import Usuario
    asignados = {a.usuario_id: a.rol_en_proyecto for a in proyecto.asignaciones.all()}
    opciones = []
    for u in Usuario.objects.filter(is_active=True).order_by("nombre_completo", "email"):
        opciones.append({
            "usuario": u,
            "asignado": u.pk in asignados,
            "rol": asignados.get(u.pk, "disenador"),
        })
    return opciones


@login_required
def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    puede_ed = puede_editar_proyecto(request.user, proyecto)
    es_htmx = _es_htmx(request)

    if request.method == "POST" and puede_ed:
        form = ProyectoForm(request.POST, instance=proyecto)
        formset = ProyectoProductoFormSetEdit(request.POST, instance=proyecto)
        if form.is_valid() and formset.is_valid():
            # Render-V2: snapshot del estado ANTES de guardar, para el Undo
            # (Redis, coalescido). Se hace sobre una instancia fresca para no
            # capturar las mutaciones que el ModelForm ya aplicó al `instance`.
            import time as _time

            from . import services_undo
            with contextlib.suppress(Exception):
                services_undo.registrar_frame(
                    Proyecto.objects.get(pk=proyecto.pk), ahora_ts=_time.time())
            form.save()
            formset.save()
            _sync_procesos_formset(formset)
            _reconciliar_equipo(request, proyecto)
            proyecto.recalcular_monto_estimado()
            proyecto.refresh_from_db()
            emitir(EventoPortavoz(
                tipo="proyecto.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "campo": "detalle_inline"},
            ))
            # C7: autoguardado HTMX → refresca panel económico + proveedores +
            # indicador + estado del Undo (OOB).
            if es_htmx:
                return render(request, "proyectos/_guardado_oob.html",
                              {"proyecto": proyecto, "ok": True,
                               "form": ProyectoForm(instance=proyecto), "puede_editar": True,
                               "proveedores_panel": _proveedores_panel(proyecto),
                               "pasos_undo": services_undo.pasos_disponibles(proyecto)})
            messages.success(request, "Proyecto guardado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
        if es_htmx:
            return render(request, "proyectos/_guardado_oob.html",
                          {"proyecto": proyecto, "ok": False,
                           "form": form, "puede_editar": True,
                           "proveedores_panel": _proveedores_panel(proyecto)}, status=200)
    else:
        form = ProyectoForm(instance=proyecto)
        formset = ProyectoProductoFormSetEdit(instance=proyecto)

    from apps.el_catalogo.models import CategoriaServicio, Proveedor
    proveedores_aplicables = list(
        Proveedor.objects.filter(
            activo=True, servicios__en_proyectos__proyecto=proyecto,
        ).distinct().order_by("razon_social")
    )
    _anotar_procesos(formset)
    from . import services_undo
    return render(request, "proyectos/detalle.html", {
        "proyecto": proyecto,
        "form": form,
        "formset": formset,
        "puede_editar": puede_ed,
        "pasos_undo": services_undo.pasos_disponibles(proyecto),
        "equipo_opciones": _ctx_equipo(proyecto),
        "roles_proyecto": ROLES_PROYECTO,
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "servicios_datos_json": _servicios_datos_json(),
        "proveedores_aplicables": proveedores_aplicables,
        "proveedores_panel": _proveedores_panel(proyecto),
        "proveedores_activos": _proveedores_activos(),
        "estados_barra": list(
            EstadoProyecto.objects.filter(activo=True).order_by("orden").values("slug", "label", "color")
        ),
        "tareas": proyecto.tareas.select_related("asignada_a").order_by("estado", "-creado_en"),
        "comentarios": _comentarios_proyecto_visibles(request.user, proyecto),
        "es_admin": es_admin(request.user),
        "ingresos_proyecto": proyecto.ingresos.filter(anulado=False).order_by("-fecha")[:50],
        "egresos_proyecto": proyecto.egresos.filter(anulado=False).select_related("proveedor").order_by("-fecha")[:50],
        "breadcrumb_items": [
            {"url": reverse("proyectos-lista"), "label": "Proyectos"},
            {"label": proyecto.codigo},
        ],
        "back_url": reverse("proyectos-lista"),
        "back_label": "Proyectos",
    })


@login_required
def resumen_actividad(request, pk):
    """El Chalán resume la actividad del proyecto (estación `comunicacion`, S4).

    GET HTMX → modal con el resumen. No persiste. Gated por ver-proyecto +
    permiso (chalan, usar)."""
    from django.utils.html import format_html

    from lib.permisos import puede_usar_chalan

    from .resumen_ia import resumir_actividad
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    if not puede_usar_chalan(request.user):
        return HttpResponseForbidden("No tienes permiso para usar El Chalán.")
    res = resumir_actividad(proyecto=proyecto, usuario=request.user)
    if res.get("ok"):
        cuerpo = format_html('<p class="whitespace-pre-line">{}</p>', res["resumen"])
    else:
        cuerpo = format_html(
            '<p class="text-error-600 dark:text-error-400">{}</p>',
            res.get("error") or "El Chalán no respondió.",
        )
    return render(request, "_componentes_tailadmin/_modal_htmx.html", {
        "titulo": f"Resumen de actividad · {proyecto.codigo}",
        "cuerpo": cuerpo,
        "tamano": "lg",
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
                _sync_procesos_formset(formset)
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
    _anotar_procesos(formset)
    return render(request, "proyectos/form.html", {
        "form": form, "formset": formset, "modo": "nuevo",
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "servicios_datos_json": _servicios_datos_json(),
        "proveedores_activos": _proveedores_activos(),
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
            _sync_procesos_formset(formset)
            proyecto.recalcular_monto_estimado()  # C4: estimado = Σ subtotales
            messages.success(request, "Proyecto actualizado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto)
        formset = ProyectoProductoFormSetEdit(instance=proyecto)
    from apps.el_catalogo.models import CategoriaServicio
    _anotar_procesos(formset)
    return render(request, "proyectos/form.html", {
        "form": form, "formset": formset, "modo": "editar", "proyecto": proyecto,
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "servicios_datos_json": _servicios_datos_json(),
        "proveedores_activos": _proveedores_activos(),
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
            # Render-V2: el cambio de estado también es un paso deshacible.
            import time as _time

            from . import services_undo
            with contextlib.suppress(Exception):
                services_undo.registrar_frame(
                    Proyecto.objects.get(pk=proyecto.pk), ahora_ts=_time.time())
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
            from . import servicios_actividad
            servicios_actividad.registrar(
                proyecto=proyecto, tipo="estado_cambiado",
                descripcion=f"Estado: {anterior} → {nuevo}", actor=request.user,
                url=f"/proyectos/{proyecto.pk}/",
            )
            if inline and es_htmx:
                # Render-V1: devolvemos la barra de status para swap inline.
                return render(request, "proyectos/_barra_status.html", {
                    "proyecto": proyecto,
                    "estados_barra": list(
                        EstadoProyecto.objects.filter(activo=True).order_by("orden").values("slug", "label", "color")
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
            from . import servicios_actividad
            servicios_actividad.registrar(
                proyecto=proyecto, tipo="tarea_creada",
                descripcion=f"Nueva tarea «{tarea.titulo[:60]}»", actor=request.user,
                url=f"/proyectos/{proyecto.pk}/",
            )
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
    from apps.el_catalogo.models import CategoriaServicio
    return render(request, "proyectos/_modal_agregar_producto.html", {
        "form": form, "proyecto": proyecto,
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
    })


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


@login_required
def agregar_proveedor_modal(request, pk):
    """C5 S-LC-Feedback-V6: asignar un proveedor (existente o nuevo) al proyecto."""
    from apps.los_proyectos.forms import ProyectoProveedorForm
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = ProyectoProveedorForm(request.POST)
        if form.is_valid():
            pv = form.save(commit=False)
            pv.proyecto = proyecto
            pv.save()
            emitir(EventoPortavoz(
                tipo="proyecto.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proyecto_id": proyecto.pk, "campo": "proveedor_asignado", "proveedor_id": pv.proveedor_id},
            ))
            messages.success(request, "Proveedor agregado al proyecto.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": _redir_detalle(proyecto)})
            return redirect(_redir_detalle(proyecto))
    else:
        form = ProyectoProveedorForm()
    return render(request, "proyectos/_modal_agregar_proveedor.html", {"form": form, "proyecto": proyecto})


@login_required
def quitar_proveedor(request, pk, prov_pk):
    from apps.los_proyectos.models import ProyectoProveedor
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    ProyectoProveedor.objects.filter(proyecto=proyecto, pk=prov_pk).delete()
    messages.success(request, "Proveedor quitado del proyecto.")
    destino = _redir_detalle(proyecto)
    if _es_htmx(request):
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(destino)


@login_required
def deshacer(request, pk):
    """Render-V2: deshace el último guardado restaurando el frame de Redis."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    from . import services_undo
    if services_undo.deshacer(proyecto):
        emitir(EventoPortavoz(
            tipo="proyecto.actualizado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"proyecto_id": proyecto.pk, "campo": "undo"},
        ))
        messages.success(request, "Se deshizo el último cambio.")
    else:
        messages.info(request, "No hay cambios que deshacer.")
    destino = _redir_detalle(proyecto)
    if _es_htmx(request):
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(destino)
