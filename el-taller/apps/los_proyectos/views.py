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
    ProyectoProductoFormSetDetalle,
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
from django.views.decorators.http import require_POST

from lib.permisos import (
    es_admin,
    puede_archivar_proyecto,
    puede_editar_proyecto,
    puede_eliminar_proyecto,
    puede_ver_finanzas,
    puede_ver_proyecto,
    roles_efectivos,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _servicios_datos_json():
    """Mapa {servicio_id: {precio, costo, categoria, proveedor_id, proveedor}}
    para que el form de Proyecto pre-llene precio/costo + PROVEEDOR al elegir un
    producto y filtre el selector por Categoría. El proveedor es el primero
    asignado al producto en el catálogo (LC 2026-07: autocompletar proveedor)."""
    import json

    from apps.el_catalogo.models import Servicio
    datos = {}
    qs = (
        Servicio.objects.filter(activo=True)
        .only("pk", "precio_base", "costo", "categoria_id")
        .prefetch_related("proveedores")
    )
    for s in qs:
        prov = next((p for p in s.proveedores.all() if p.activo), None)
        datos[str(s.pk)] = {
            "precio": str(s.precio_base or 0),
            "costo": str(s.costo or 0),
            "categoria": str(s.categoria_id or ""),
            "proveedor_id": str(prov.pk) if prov else "",
            "proveedor": prov.razon_social if prov else "",
        }
    return json.dumps(datos)


def _proveedores_activos():
    """Proveedores activos para los selects (principal + impresión)."""
    from apps.el_catalogo.models import Proveedor
    return list(Proveedor.objects.filter(activo=True).order_by("razon_social"))


def _proveedores_panel(proyecto):
    """Panel de proveedores del proyecto (reporte Oscar, redISEÑO):

    Por proveedor: total sin IVA, toggle de IVA propio del proyecto (default
    prendido), total con IVA, y los CONCEPTOS que nos provee (producto o
    impresión) con `cantidad (piezas-con-merma)` y costo unitario. Fusiona la
    asignación explícita (tipo entregan/recogemos, compromiso, contacto)."""
    iva_fraccion = proyecto.iva_tasa_efectiva
    # Toggle de IVA por proveedor — solo este proyecto. Sin fila ⇒ True.
    iva_map = {r.proveedor_id: r.aplica_iva for r in proyecto.proveedores_iva.all()}
    asignados = {
        pv.proveedor_id: pv
        for pv in proyecto.proveedores_asignados.select_related("proveedor").all()
    }
    acc: dict[int, dict] = {}

    def _slot(prov):
        return acc.setdefault(
            prov.pk, {"proveedor": prov, "total": Decimal("0.00"), "conceptos": []}
        )

    for pp in proyecto.productos_incluidos:
        piezas = pp.cantidad + pp.merma
        nombre_prod = pp.servicio.nombre if pp.servicio_id else "Producto"
        if pp.proveedor_id:
            s = _slot(pp.proveedor)
            s["total"] += pp.costo_total_linea
            s["conceptos"].append({
                "nombre": nombre_prod, "cantidad": pp.cantidad, "piezas": piezas,
                "costo_unit": pp.costo_efectivo, "fijo": None,
            })
        for proc in pp.procesos.all():
            if proc.tipo == "impresion" and proc.proveedor_id:
                s = _slot(proc.proveedor)
                c = Decimal(str(proc.costo or 0))
                nombre = f"Impresión · {nombre_prod}"
                if proc.por_pieza:
                    s["total"] += c * piezas
                    s["conceptos"].append({
                        "nombre": nombre, "cantidad": pp.cantidad, "piezas": piezas,
                        "costo_unit": c, "fijo": None,
                    })
                else:
                    s["total"] += c
                    s["conceptos"].append({
                        "nombre": nombre, "cantidad": None, "piezas": None,
                        "costo_unit": None, "fijo": c,
                    })

    def _fila(prov, total, conceptos, asignacion):
        aplica = iva_map.get(prov.pk, True)
        total = total.quantize(Decimal("0.01"))
        iva = (total * iva_fraccion).quantize(Decimal("0.01")) if aplica else Decimal("0.00")
        return {
            "proveedor": prov, "total": total, "aplica_iva": aplica, "iva": iva,
            "total_con_iva": (total + iva).quantize(Decimal("0.01")),
            "conceptos": conceptos, "asignacion": asignacion,
        }

    filas, vistos = [], set()
    for pid, s in sorted(acc.items(), key=lambda kv: kv[1]["total"], reverse=True):
        vistos.add(pid)
        filas.append(_fila(s["proveedor"], s["total"], s["conceptos"], asignados.get(pid)))
    for pid, pv in asignados.items():
        if pid not in vistos:
            filas.append(_fila(pv.proveedor, Decimal("0.00"), [], pv))
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


def _proyectos_visibles(user, *, solo_archivados=False):
    """Queryset filtrado por rol. Por default EXCLUYE archivados (LC 2026-07);
    con `solo_archivados=True` devuelve únicamente los archivados."""
    # V6 Bloque 10: roles efectivos (rol primario + roles_extra) en lugar de
    # user.rol duro — un "miembro" con rol personalizado "dueno" ve lo mismo.
    roles = roles_efectivos(user)
    base = Proyecto.objects.filter(archivado=True) if solo_archivados else Proyecto.activos.all()
    qs = base.select_related("cliente")
    if roles & {"super_admin", "dueno", "contador"}:
        return qs
    if "disenador" in roles:
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
    ver_archivados = request.GET.get("archivados") == "1"
    qs = _proyectos_visibles(request.user, solo_archivados=ver_archivados)
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
    if ver_archivados:
        qs_filtros.append("archivados=1")
    querystring_base = "&".join(qs_filtros)
    archivados_count = _proyectos_visibles(request.user, solo_archivados=True).count()

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
        "ver_archivados": ver_archivados,
        "archivados_count": archivados_count,
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
    # LC Buzón §158/159: «En pausa» va primero en la fila inferior.
    SLUGS_FILA_ABAJO = ("en_pausa", "entregado", "cerrado", "cancelado")
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
    """Equipo agrupado por rol (S-LC-Feedback-V7): una o varias personas por
    rol. Checkbox `equipo__<rol>` con value=<userpk>. Si una persona queda
    marcada en dos roles gana el último en ROLES_PROYECTO (la asignación es
    1 fila por persona por el UniqueConstraint proyecto+usuario)."""
    from cuentas.models.usuario import Usuario
    roles_validos = dict(ROLES_PROYECTO)
    activos = {u.pk: u for u in Usuario.objects.filter(is_active=True)}
    deseado: dict[int, str] = {}
    for slug in roles_validos:
        for pk_s in request.POST.getlist(f"equipo__{slug}"):
            try:
                pk = int(pk_s)
            except (TypeError, ValueError):
                continue
            if pk in activos:
                deseado[pk] = slug
    actuales = {a.usuario_id: a for a in proyecto.asignaciones.all()}
    for pk, rol in deseado.items():
        a = actuales.get(pk)
        if a is None:
            ProyectoAsignacion.objects.create(proyecto=proyecto, usuario=activos[pk], rol_en_proyecto=rol)
        elif a.rol_en_proyecto != rol:
            a.rol_en_proyecto = rol
            a.save(update_fields=["rol_en_proyecto"])
    for pk, a in actuales.items():
        if pk not in deseado:
            a.delete()


def _comentarios_proyecto_visibles(user, proyecto):
    """Comentarios del proyecto filtrados por visibilidad (es_interno)."""
    from lib.permisos import puede_ver_comentario
    qs = proyecto.comentarios.select_related("autor").order_by("creado_en")
    return [c for c in qs if puede_ver_comentario(user, c)]


def _ctx_equipo(proyecto):
    """Lista plana de usuarios activos con su estado asignado/rol — usada por la
    vista de SOLO LECTURA del detalle (sidebar de equipo del diseñador)."""
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


def _ctx_equipo_grupos(proyecto):
    """Equipo AGRUPADO POR ROL para el widget editable del detalle
    (S-LC-Feedback-V7). Para cada rol, todas las personas activas con un
    checkbox; permite elegir una o varias personas por rol."""
    from cuentas.models.usuario import Usuario
    asignados = {a.usuario_id: a.rol_en_proyecto for a in proyecto.asignaciones.all()}
    usuarios = list(Usuario.objects.filter(is_active=True).order_by("nombre_completo", "email"))
    grupos = []
    for slug, label in ROLES_PROYECTO:
        grupos.append({
            "slug": slug,
            "label": label,
            "personas": [{"usuario": u, "marcado": asignados.get(u.pk) == slug} for u in usuarios],
        })
    return grupos


@login_required
def _primer_error(form, formset) -> str:
    """Primer error legible del form o del formset, para el indicador del
    autosave (V6 Bloque 5). '' si no hay (no debería pasar en rama inválida)."""
    for f in [form, *formset.forms]:
        for campo, errores in f.errors.items():
            etiqueta = "" if campo == "__all__" else f"{f.fields.get(campo).label if f.fields.get(campo) else campo}: "
            if errores:
                return f"{etiqueta}{errores[0]}"
    for e in formset.non_form_errors():
        return str(e)
    return ""


def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    puede_ed = puede_editar_proyecto(request.user, proyecto)
    es_htmx = _es_htmx(request)

    if request.method == "POST" and puede_ed:
        form = ProyectoForm(request.POST, instance=proyecto)
        formset = ProyectoProductoFormSetDetalle(request.POST, instance=proyecto)
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
            # ¿Se creó algún producto inline? Entonces hay que re-renderizar el
            # formset por OOB para que la tarjeta nueva traiga su pk y NO se
            # duplique en el siguiente autosave (bug que motivó el modal en V8).
            hubo_nuevos = bool(getattr(formset, "new_objects", None))
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
                ctx = {"proyecto": proyecto, "ok": True,
                       "form": ProyectoForm(instance=proyecto), "puede_editar": True,
                       "proveedores_panel": _proveedores_panel(proyecto),
                       "pasos_undo": services_undo.pasos_disponibles(proyecto)}
                if hubo_nuevos:
                    from apps.el_catalogo.models import CategoriaServicio
                    nuevo_fs = ProyectoProductoFormSetDetalle(instance=proyecto)
                    _anotar_procesos(nuevo_fs)
                    ctx.update({
                        "rerender_productos": True,
                        "formset": nuevo_fs,
                        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
                        "proveedores_activos": _proveedores_activos(),
                    })
                return render(request, "proyectos/_guardado_oob.html", ctx)
            messages.success(request, "Proyecto guardado.")
            return redirect("proyectos-detalle", pk=proyecto.pk)
        if es_htmx:
            # V6 Bloque 5: el autosave fallido era silencioso (solo "✕") y el
            # usuario creía que su cambio (p.ej. el toggle de incluir) se había
            # guardado. Ahora el OOB lleva el primer error legible.
            return render(request, "proyectos/_guardado_oob.html",
                          {"proyecto": proyecto, "ok": False,
                           "form": form, "puede_editar": True,
                           "error_detalle": _primer_error(form, formset),
                           "proveedores_panel": _proveedores_panel(proyecto)}, status=200)
    else:
        form = ProyectoForm(instance=proyecto)
        formset = ProyectoProductoFormSetDetalle(instance=proyecto)

    from apps.el_catalogo.models import CategoriaServicio, Proveedor
    proveedores_aplicables = list(
        Proveedor.objects.filter(
            activo=True, servicios__en_proyectos__proyecto=proyecto,
        ).distinct().order_by("razon_social")
    )
    _anotar_procesos(formset)
    from . import gastos, services_undo
    # LC 2026-07: la alerta pasa a "pagos pendientes sin registrar" y vive
    # abajo, en el recuadro de egresos. Sale de producción en adelante.
    pagos_pendientes = gastos.pagos_pendientes_de(proyecto) if gastos.debe_mostrar_alerta_pagos(proyecto) else []
    pagos_desglose = gastos.desglose_iva(proyecto, pagos_pendientes) if pagos_pendientes else None
    return render(request, "proyectos/detalle.html", {
        "proyecto": proyecto,
        "form": form,
        "formset": formset,
        "puede_editar": puede_ed,
        "pagos_pendientes": pagos_pendientes,
        "pagos_desglose": pagos_desglose,
        "pagos_pendientes_total": sum((g["monto"] for g in pagos_pendientes), Decimal("0.00")),
        "pasos_undo": services_undo.pasos_disponibles(proyecto),
        "equipo_opciones": _ctx_equipo(proyecto),
        "equipo_grupos": _ctx_equipo_grupos(proyecto),
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
        "puede_archivar_proyecto": puede_archivar_proyecto(request.user),
        "puede_eliminar_proyecto": puede_eliminar_proyecto(request.user),
        "ingresos_proyecto": proyecto.ingresos.filter(anulado=False).order_by("-fecha")[:50],
        "egresos_proyecto": proyecto.egresos.filter(anulado=False).select_related("proveedor").order_by("-fecha")[:50],
        "breadcrumb_items": [
            {"url": reverse("proyectos-lista"), "label": "Proyectos"},
            {"label": proyecto.codigo},
        ],
        "back_url": reverse("proyectos-lista"),
        "back_label": "Proyectos",
        # Recuadro «Cotizaciones» (versionado, render Oscar 2026-06-27).
        **_ctx_cotizaciones(proyecto, request.user),
        # Recuadro «Facturas ligadas» (LC #9).
        **_ctx_facturas(proyecto, request.user),
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
        # Fecha de compromiso precargada desde el Calendario
        # (?fecha_compromiso=YYYY-MM-DD). LC 2026-06-29.
        initial = {}
        f = request.GET.get("fecha_compromiso")
        if f:
            initial["fecha_compromiso_dia"] = f
        form = ProyectoForm(initial=initial)
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
            from apps.la_cartera.services import asegurar_contacto_principal
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            asegurar_contacto_principal(cliente)
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
def duplicar(request, pk):
    """Clona un proyecto completo con nombre nuevo (LC 2026-07). Patrón Wave 5:
    GET HTMX → modal; POST → crea y redirige al nuevo proyecto."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, None):
        return HttpResponseForbidden("Sin permiso para crear proyectos.")
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        from .services_duplicar import duplicar_proyecto
        nombre = (request.POST.get("nombre") or "").strip() or f"Copia de {proyecto.nombre}"
        nuevo = duplicar_proyecto(proyecto, nombre=nombre, actor=request.user)
        messages.success(request, f"Proyecto duplicado como {nuevo.codigo} · {nuevo.nombre}.")
        destino = reverse("proyectos-detalle", args=[nuevo.pk])
        return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
    return render(request, "proyectos/_modal_duplicar.html", {"proyecto": proyecto})


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


def _proyecto_tiene_movimientos(proyecto) -> bool:
    """True si el proyecto tiene facturas/ingresos/egresos ligados (no se puede
    borrar permanentemente; solo archivar)."""
    return (
        proyecto.facturas.exists()
        or proyecto.ingresos.exists()
        or proyecto.egresos.exists()
    )


@login_required
def archivar(request, pk):
    """Archiva/reactiva un proyecto (soft, reversible). Oculta de listas, kanban
    y selectores. Distinto de «Cancelado» (estado real). Patrón Wave 5."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_archivar_proyecto(request.user):
        return HttpResponseForbidden("Sin permiso para archivar proyectos.")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        proyecto.archivado = not proyecto.archivado
        if proyecto.archivado:
            proyecto.archivado_en = timezone.now()
            proyecto.archivado_por = request.user
        else:
            proyecto.archivado_en = None
            proyecto.archivado_por = None
        proyecto.save(update_fields=["archivado", "archivado_en", "archivado_por", "actualizado_en"])
        emitir(EventoPortavoz(
            tipo="proyecto.archivado" if proyecto.archivado else "proyecto.reactivado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo},
        ))
        if proyecto.archivado:
            messages.success(request, f"Proyecto {proyecto.codigo} archivado.")
            destino = reverse("proyectos-lista")
        else:
            messages.success(request, f"Proyecto {proyecto.codigo} reactivado.")
            destino = _redir_detalle(proyecto)
        return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
    if es_htmx:
        return render(request, "proyectos/_modal_archivar.html", {"proyecto": proyecto})
    return redirect(_redir_detalle(proyecto))


@login_required
def eliminar(request, pk):
    """Borrado PERMANENTE (super_admin, solo proyectos sin movimientos
    financieros). Para proyectos de prueba/duplicados. Patrón Wave 5."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_eliminar_proyecto(request.user):
        return HttpResponseForbidden("Solo un super administrador puede eliminar proyectos.")
    es_htmx = _es_htmx(request)
    tiene_mov = _proyecto_tiene_movimientos(proyecto)
    if request.method == "POST":
        if tiene_mov:
            messages.error(request, "No se puede eliminar: el proyecto tiene facturas/ingresos/egresos ligados. Archívalo en su lugar.")
            destino = _redir_detalle(proyecto)
            return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
        codigo = proyecto.codigo
        emitir(EventoPortavoz(
            tipo="proyecto.eliminado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"codigo": codigo, "nombre": proyecto.nombre},
        ))
        proyecto.delete()
        messages.success(request, f"Proyecto {codigo} eliminado permanentemente.")
        destino = reverse("proyectos-lista")
        return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
    if es_htmx:
        return render(request, "proyectos/_modal_eliminar.html",
                      {"proyecto": proyecto, "tiene_movimientos": tiene_mov})
    return redirect(_redir_detalle(proyecto))


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
            tarea.creado_por = request.user
            tarea.save()
            from apps.el_pizarron import runners
            runners.aplicar_desde_form(tarea, form.cleaned_data, actor=request.user)
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
    destino = _redir_detalle(proyecto)
    # V2: la X del desglose económico usa HTMX → recarga consistente (la página
    # se re-renderiza desde la DB, sin desincronizar el sidebar con las tarjetas).
    if _es_htmx(request):
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(destino)


# ── Cotizaciones del proyecto (recuadro versionado, render Oscar 2026-06-27) ──

# El botón "Enviar" del recuadro aún no manda correo real (El Cartero ya existe,
# se cablea después). Por ahora es placeholder → rickroll (decisión Oscar).
RICKROLL_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _ctx_facturas(proyecto, user) -> dict:
    """Contexto del recuadro «Facturas ligadas» del detalle de proyecto (LC #9).

    Lista las facturas del proyecto (incl. canceladas, atenuadas), más recientes
    primero. `puede_facturar` habilita el botón «+ Nueva»."""
    from lib.permisos import puede_crear_facturacion
    facturas = list(proyecto.facturas.select_related("cliente").order_by("-creado_en")[:20])
    return {
        "facturas_proyecto": facturas,
        "puede_facturar": puede_crear_facturacion(user),
    }


def _ctx_cotizaciones(proyecto, user) -> dict:
    """Contexto del recuadro «Cotizaciones» del detalle de proyecto.

    El estatus es ÚNICO para la cotización del proyecto (vive en la versión más
    reciente, la única editable). El pizza-tracker pinta los pasos CONFIGURADOS
    en Gerencia (EstadoCotizacion activos, ordenados): los previos como 'done',
    el actual 'current' y los siguientes 'future'. Crece/encoge según cuántos
    pasos haya. Las versiones pasadas muestran un círculo de color = su último
    estado (solo lectura); solo la más reciente cambia de estatus (LC 2026-06-30).
    """
    from apps.cotizaciones.models import estados_cot_activos, mapa_estados_cot

    from lib.permisos import (
        puede_crear_cotizaciones,
        puede_editar_cotizaciones,
        puede_ver_cotizaciones,
    )
    cots = list(proyecto.cotizaciones.filter(version__gt=0).order_by("version"))
    latest = cots[-1] if cots else None
    activos = estados_cot_activos()
    mapa = mapa_estados_cot()
    estado_actual = latest.estado if latest else None

    def _tracker_de(estado):
        """Pasos configurados con fase done/current/future según `estado`."""
        idx = next((i for i, e in enumerate(activos) if e["slug"] == estado), None)
        out = []
        for i, e in enumerate(activos):
            fase = ("future" if idx is None else
                    ("done" if i < idx else ("current" if i == idx else "future")))
            out.append({**e, "fase": fase, "num": i + 1})
        return out

    # LC 2026-07 (D3): CADA versión lleva su propio tracker (dentro de su
    # desplegable). La versión activa abre por default; las pasadas, cerradas.
    for c in cots:
        c.tracker_steps = _tracker_de(c.estado)
    tracker = _tracker_de(estado_actual)  # compat con el resto del contexto
    ts = None
    if latest:
        ts = {
            "enviada": latest.enviada_en,
            "aprobada": latest.aprobada_en,
            "pagada": latest.pagada_en,
        }.get(estado_actual) or latest.creado_en
    return {
        "proyecto": proyecto,
        "cotizaciones_proyecto": cots,
        "cot_latest_pk": latest.pk if latest else None,
        "cot_estado_actual": estado_actual,
        "cot_estado_label": (mapa.get(estado_actual) or {}).get("label", estado_actual or ""),
        "cot_estado_color": (mapa.get(estado_actual) or {}).get("color", "#667085"),
        "cot_estados_activos": activos,
        "cot_tracker": tracker,
        "cot_estado_ts_fmt": _fmt_fechahora(ts),
        "cot_next_version": (latest.version + 1) if latest else 1,
        "puede_cotizar": puede_crear_cotizaciones(user),
        "puede_estado": puede_editar_cotizaciones(user),
        "ver_cotizaciones": puede_ver_cotizaciones(user),
        # S-LC-Feedback-V13: cuando el estatus es «anticipo» se ofrece registrar
        # el ingreso del anticipo (botón en el recuadro). cot_total alimenta los
        # atajos de 50%/etc. del modal.
        "cot_es_anticipo": estado_actual == "anticipo",
        "cot_total": (latest.calcular_totales()["total"] if latest else 0),
        "puede_anticipo": puede_ver_finanzas(user),
        "rickroll_url": RICKROLL_URL,
    }


@login_required
@require_POST
def generar_cotizacion(request, pk):
    """Genera la siguiente versión de cotización del proyecto desde los
    Productos involucrados actuales (snapshot). Devuelve el recuadro re-render."""
    from lib.permisos import puede_crear_cotizaciones
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    if not puede_crear_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para crear cotizaciones.")
    from apps.cotizaciones import services as cot_services
    cot = cot_services.generar_desde_proyecto(proyecto, request.user)
    messages.success(request, f"Cotización {cot.version_label} generada ({cot.codigo}).")
    if _es_htmx(request):
        return render(request, "proyectos/_cotizaciones_panel.html",
                      _ctx_cotizaciones(proyecto, request.user))
    return redirect(_redir_detalle(proyecto))


@login_required
@require_POST
def cotizacion_estado(request, pk):
    """Cambia el estatus ÚNICO de la cotización del proyecto. Opera sobre la
    versión más reciente (la única editable): lo dispara el dropdown de la
    última versión o el pizza-tracker. Devuelve el recuadro re-renderizado."""
    from apps.cotizaciones import services as cot_services
    from apps.cotizaciones.models import Cotizacion

    from lib.permisos import puede_editar_cotizaciones
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    if not puede_editar_cotizaciones(request.user):
        return HttpResponseForbidden("Sin permiso para editar cotizaciones.")
    # LC 2026-07 (D3): puede venir `cot_pk` para cambiar el estado de UNA versión
    # concreta (cada versión tiene su tracker). Sin él, opera sobre la más reciente.
    cot_pk = request.POST.get("cot_pk")
    if cot_pk:
        objetivo = Cotizacion.objects.filter(proyecto=proyecto, pk=cot_pk, version__gt=0).first()
    else:
        objetivo = (
            Cotizacion.objects.filter(proyecto=proyecto, version__gt=0)
            .order_by("-version").first()
        )
    if objetivo is None:
        messages.error(request, "No hay cotizaciones generadas todavía.")
    else:
        try:
            cot_services.marcar_estado_proyecto(objetivo, request.POST.get("estado", ""), request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
    if _es_htmx(request):
        return render(request, "proyectos/_cotizaciones_panel.html",
                      _ctx_cotizaciones(proyecto, request.user))
    return redirect(_redir_detalle(proyecto))


@login_required
def registrar_anticipo_modal(request, pk):
    """S-LC-Feedback-V13 — modal para registrar el INGRESO del anticipo de la
    cotización del proyecto. Sin monto predeterminado: la UI ofrece botones
    rápidos (25/50/100% del total) o monto personalizado. El ingreso queda
    ligado al proyecto. Gated por finanzas (mismo permiso que Tesorería)."""
    from apps.cotizaciones.models import Cotizacion
    from django.utils import timezone

    from .forms import RegistrarAnticipoForm
    proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=pk)
    if not puede_ver_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin acceso a este proyecto.")
    if not puede_ver_finanzas(request.user):
        return HttpResponseForbidden("Sin permiso para registrar ingresos.")
    latest = (
        Cotizacion.objects.filter(proyecto=proyecto, version__gt=0)
        .order_by("-version")
        .first()
    )
    total = latest.calcular_totales()["total"] if latest else Decimal("0.00")
    es_htmx = _es_htmx(request)
    if request.method == "POST":
        form = RegistrarAnticipoForm(request.POST)
        if form.is_valid():
            from apps.tesoreria.models import Ingreso
            ref = latest.codigo if latest else proyecto.codigo
            ing = Ingreso.objects.create(
                proyecto=proyecto,
                cliente=proyecto.cliente,
                monto=form.cleaned_data["monto"],
                fecha=form.cleaned_data["fecha"],
                metodo=form.cleaned_data["metodo"],
                descripcion=f"Anticipo · {ref}",
                referencia_externa=f"Anticipo {ref}"[:100],
                creado_por=request.user if request.user.is_authenticated else None,
            )
            emitir(EventoPortavoz(
                tipo="tesoreria.ingreso_registrado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"ingreso_id": ing.pk, "proyecto_id": proyecto.pk, "origen": "anticipo"},
            ))
            messages.success(request, f"Anticipo registrado en {proyecto.codigo}.")
            destino = _redir_detalle(proyecto)
            return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
        return render(request, "proyectos/_modal_registrar_anticipo.html",
                      {"proyecto": proyecto, "form": form, "cot_total": total, "cot": latest})
    form = RegistrarAnticipoForm(initial={"fecha": timezone.localdate(), "metodo": "transferencia"})
    return render(request, "proyectos/_modal_registrar_anticipo.html",
                  {"proyecto": proyecto, "form": form, "cot_total": total, "cot": latest})


@login_required
def toggle_proveedor_iva(request, pk, prov_pk):
    """Prende/apaga el IVA de un proveedor, SOLO en este proyecto (reporte Oscar).

    Sin fila = IVA prendido (default). Primer toggle crea la fila en False; los
    siguientes la voltean. Devuelve el panel de proveedores por OOB."""
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProveedorIva
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not puede_editar_proyecto(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso.")
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    prov = get_object_or_404(Proveedor, pk=prov_pk)
    obj, creado = ProyectoProveedorIva.objects.get_or_create(
        proyecto=proyecto, proveedor=prov, defaults={"aplica_iva": False},
    )
    if not creado:
        obj.aplica_iva = not obj.aplica_iva
        obj.save(update_fields=["aplica_iva"])
    return render(request, "proyectos/_proveedores_panel.html", {
        "proyecto": proyecto, "proveedores_panel": _proveedores_panel(proyecto),
        "puede_editar": True, "oob": True,
    })


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


# ── Gastos no registrados → egresos (contabilidad en línea) ──────────────

def _puede_registrar_gastos(user, proyecto) -> bool:
    """Puede registrar gastos quien edita el proyecto O quien lleva finanzas
    (contador desde la página de Tesorería)."""
    return puede_editar_proyecto(user, proyecto) or puede_ver_finanzas(user)


def _destino_registro(request, proyecto):
    if (request.POST.get("volver") or "").strip() == "tesoreria":
        return reverse("tesoreria:gastos-no-registrados")
    return reverse("proyectos-detalle", args=[proyecto.pk])


@login_required
def registrar_gasto_modal(request, pk, clase, obj_pk):
    """GET/POST modal «Registrar pago» de un gasto del proyecto (LC 2026-07).

    Pide FECHA, proveedor (OBLIGATORIO), método y estado (Pagado por default,
    solo Pagado/Por reembolsar — un egreso solo se registra al realizarse).
    Si el gasto ya tiene un egreso «Pendiente» (cuenta por pagar auto-generada)
    lo LIQUIDA; si no tiene egreso, lo crea ya pagado."""
    from datetime import date as _date

    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not _puede_registrar_gastos(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso para registrar gastos del proyecto.")
    if clase not in ("producto", "proceso"):
        return HttpResponseForbidden("Tipo de gasto inválido.")
    from decimal import Decimal

    from apps.el_catalogo.models import Proveedor
    from apps.tesoreria.models import CentroDeCosto
    from apps.tesoreria.models.egreso import (
        METODOS_EGRESO,
        METODOS_EGRESO_FORM,
        METODOS_REEMBOLSO,
    )

    from cuentas.models.usuario import Usuario

    from . import gastos
    info = gastos.datos_para_modal(proyecto, clase, obj_pk)
    if info is None:
        return HttpResponseForbidden("Gasto no encontrado.")

    # LC #16: método por defecto «Tarjeta empresa»; métodos personales que, al
    # elegirse, mutan el estado a «Por reembolsar» (front + back).
    METODO_DEFAULT = "tarjeta_empresa"
    METODOS_PERSONALES = set(METODOS_REEMBOLSO)
    # Pares (valor, etiqueta) del subconjunto del form (METODOS_EGRESO_FORM son
    # sólo valores; las etiquetas viven en METODOS_EGRESO).
    _labels_metodo = dict(METODOS_EGRESO)
    METODOS_FORM_PARES = [(v, _labels_metodo.get(v, v)) for v in METODOS_EGRESO_FORM]
    # Solo dos estados: Pagado (default) y Por reembolsar.
    ESTADOS_PAGO_UI = [("pagado", "Pagado (saldado)"),
                       ("por_reembolsar", "Por reembolsar al empleado")]

    # LC #163: desglose de IVA para el hero (informativo — la tasa efectiva del
    # proyecto sobre la base del gasto).
    _tasa = Decimal(str(getattr(proyecto, "iva_tasa_efectiva", 0) or 0))
    _base = Decimal(str(info["monto"] or 0))
    _iva = (_base * _tasa).quantize(Decimal("0.01"))
    # LC #16: «¿Quién solicitó?» se pre-puebla con el Líder del proyecto.
    _lider = (proyecto.asignaciones.filter(rol_en_proyecto="lider")
              .select_related("usuario").first())

    def _ctx(error=None):
        return {
            "proyecto": proyecto, "clase": clase, "obj_pk": obj_pk, "info": info,
            "centros": CentroDeCosto.objects.filter(activo=True).order_by("nombre"),
            "centro_default": CentroDeCosto.objects.filter(slug=gastos.CENTRO_SLUG).first(),
            "metodos": METODOS_FORM_PARES, "estados_pago": ESTADOS_PAGO_UI,
            "metodo_default": METODO_DEFAULT,
            "metodos_personales": list(METODOS_PERSONALES),
            "hoy": _date.today().isoformat(),
            "usuarios": Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
            "proveedores": Proveedor.objects.filter(activo=True).order_by("razon_social"),
            "iva_monto": _iva, "iva_label": f"{float(_tasa * 100):g}%",
            "total_con_iva": (_base + _iva).quantize(Decimal("0.01")),
            "solicitado_por_default": _lider.usuario_id if _lider else None,
            "error": error,
        }

    if request.method == "POST":
        centro = CentroDeCosto.objects.filter(pk=request.POST.get("centro_de_costo") or 0).first()
        pagado = Usuario.objects.filter(pk=request.POST.get("pagado_por") or 0).first()
        proveedor = Proveedor.objects.filter(
            pk=request.POST.get("proveedor") or 0, activo=True).first()
        metodo = request.POST.get("metodo") or METODO_DEFAULT
        estado_pago = request.POST.get("estado_pago") or "pagado"
        if estado_pago not in ("pagado", "por_reembolsar"):
            estado_pago = "pagado"
        # LC #16: método personal ⇒ el gasto queda «Por reembolsar» (defensa
        # server-side; el front también lo muta).
        if metodo in METODOS_PERSONALES:
            estado_pago = "por_reembolsar"
        solicitado = Usuario.objects.filter(pk=request.POST.get("solicitado_por") or 0).first()
        # Fecha del pago (nuevo campo).
        fecha = _date.today()
        raw_fecha = (request.POST.get("fecha") or "").strip()
        if raw_fecha:
            with contextlib.suppress(ValueError):
                fecha = _date.fromisoformat(raw_fecha)
        # Proveedor OBLIGATORIO (LC 2026-07).
        if proveedor is None:
            return render(request, "proyectos/_modal_registrar_gasto.html",
                          _ctx(error="Elige un proveedor: todo egreso debe ir ligado a uno."),
                          status=200)

        egreso_pend = info.get("egreso") if info.get("pendiente") else None
        if egreso_pend is not None:
            # Liquidar la cuenta por pagar auto-generada.
            campos_pend = []
            if proveedor is not None and egreso_pend.proveedor_id != proveedor.pk:
                egreso_pend.proveedor = proveedor
                egreso_pend.proveedor_nombre = (proveedor.razon_social or "")[:200]
                campos_pend += ["proveedor", "proveedor_nombre"]
            if solicitado is not None and egreso_pend.solicitado_por_id != solicitado.pk:
                egreso_pend.solicitado_por = solicitado
                campos_pend.append("solicitado_por")
            if campos_pend:
                egreso_pend.save(update_fields=campos_pend + ["actualizado_en"])
            from apps.tesoreria.services import liquidar_egreso_pendiente
            banco_o_caja = "caja" if metodo == "efectivo" else "banco"
            liquidar_egreso_pendiente(
                egreso_pend, estado_destino=estado_pago, metodo=metodo,
                banco_o_caja=banco_o_caja, fecha=fecha, pagado_por=pagado,
                actor=request.user,
            )
            messages.success(request, f"Pago registrado en el egreso {egreso_pend.codigo}.")
        else:
            eg = gastos.registrar_egreso(
                proyecto, clase, obj_pk, actor=request.user,
                centro=centro, metodo=metodo, estado_pago=estado_pago,
                pagado_por=pagado, proveedor=proveedor, fecha=fecha,
                solicitado_por=solicitado,
            )
            if eg is None:
                return render(request, "proyectos/_modal_registrar_gasto.html",
                              _ctx(error="No se pudo registrar (revisa el centro de costo)."),
                              status=200)
            messages.success(request, f"Pago registrado como egreso {eg.codigo}.")

        destino = _destino_registro(request, proyecto)
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(status=204, headers={"HX-Redirect": destino})
        return redirect(destino)

    return render(request, "proyectos/_modal_registrar_gasto.html", _ctx())


@login_required
@require_POST
def registrar_gasto(request, pk, clase, obj_pk):
    """Registra UNA unidad de gasto del proyecto como egreso de Tesorería
    (atajo POST directo, sin modal — usado por fallback/no-HTMX)."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not _puede_registrar_gastos(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso para registrar gastos del proyecto.")
    from . import gastos
    if clase not in ("producto", "proceso"):
        messages.error(request, "Tipo de gasto inválido.")
        return redirect("proyectos-detalle", pk=proyecto.pk)
    eg = gastos.registrar_egreso(proyecto, clase, obj_pk, actor=request.user)
    if eg is None:
        messages.error(
            request,
            "No se pudo registrar el gasto. Verifica que exista el centro de costo "
            "«insumos-de-proyecto» y que el monto sea mayor a cero.",
        )
    else:
        messages.success(request, f"Gasto registrado como egreso {eg.codigo}.")
    return redirect(_destino_registro(request, proyecto))


@login_required
@require_POST
def registrar_gastos_todos(request, pk):
    """Registra TODOS los gastos pendientes del proyecto de una vez."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not _puede_registrar_gastos(request.user, proyecto):
        return HttpResponseForbidden("Sin permiso para registrar gastos del proyecto.")
    from . import gastos
    creados = gastos.registrar_pendientes(proyecto, actor=request.user)
    if creados:
        messages.success(request, f"{len(creados)} gasto(s) registrado(s) en Tesorería.")
    else:
        messages.info(request, "No había gastos pendientes (o falta el centro de costo).")
    return redirect(_destino_registro(request, proyecto))
