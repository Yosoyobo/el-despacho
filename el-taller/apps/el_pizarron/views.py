import re

from apps.el_pizarron.forms import ComentarioForm, TareaForm, TareaGlobalForm
from apps.el_pizarron.models import Tarea
from apps.los_proyectos.models import Proyecto
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from lib.busqueda import q_texto
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


def _origen_de_la_visita(request) -> str:
    """De dónde viene quien abrió esta página, como ruta interna o "".

    Primero el `?volver=` explícito (lo pegan las listas con `con_volver`) y si no
    hay, la cabecera `Referer`. El referer es el que hace que funcione cuando
    alguien llega picando un enlace que no lleva el parámetro; el parámetro es el
    que hace que siga funcionando cuando el navegador no manda referer.

    Sólo se aceptan rutas internas (`es_ruta_interna`): un `volver` a otro
    dominio sería un redirect abierto.
    """
    from urllib.parse import urlparse

    from lib.navegacion import LLAVES, es_ruta_interna

    for llave in LLAVES:
        valor = request.GET.get(llave)
        if es_ruta_interna(valor):
            return str(valor).strip()

    referer = request.META.get("HTTP_REFERER") or ""
    if not referer:
        return ""
    try:
        partes = urlparse(referer)
    except ValueError:
        return ""
    # Sólo de nuestro propio host: un referer externo no dice nada del recorrido.
    if partes.netloc and partes.netloc != request.get_host():
        return ""
    ruta = partes.path + (f"?{partes.query}" if partes.query else "")
    return ruta if es_ruta_interna(ruta) else ""


#: De dónde se puede llegar a una tarea, y a dónde hay que devolver a quien vino
#: de ahí. El orden importa: la primera que casa gana, así que las rutas más
#: específicas van antes.
_ORIGENES_TAREA = (
    ("/mandados/", "Mandados", "mandados-lista"),
    ("/tareas/", "Tareas", "tareas-kanban"),
)

#: Las páginas de UNA tarea concreta (`/tareas/12/`, `/tareas/12/editar`) NO son
#: un origen válido. Sin esto, al guardar una edición el referer sería el propio
#: formulario y el botón de volver te regresaría a él — un callejón.
_RE_PAGINA_DE_UNA = re.compile(r"^/(tareas|mandados)/\d+")



def _rastro_util(request) -> str:
    """El primer rastro de navegación que sirve para volver, o "".

    Se prueban en orden el campo oculto del form, el `?volver=` y el referer, y se
    descarta cualquiera que apunte a la pantalla de UNA tarea. Ese descarte es el
    que importa en un POST: ahí el referer es el propio formulario, así que sin
    filtrarlo el botón de volver devolvería al form que se acaba de enviar.
    """
    from lib.navegacion import es_ruta_interna

    candidatos = [
        request.POST.get("volver", "") if request.method == "POST" else "",
        request.GET.get("volver", ""),
        _origen_de_la_visita(request),
    ]
    for c in candidatos:
        c = (c or "").strip()
        if es_ruta_interna(c) and not _RE_PAGINA_DE_UNA.match(c):
            return c
    return ""


def _navegacion_tarea(request, tarea) -> dict:
    """Migas y botón de regreso de una tarea, según de dónde se llegó.

    Oscar (2026-08-23): «cuando edito una tarea el breadcrumb regresa al
    proyecto, eso está mal; si empiezo en tareas, debo regresar a tareas».

    Antes las migas estaban CLAVADAS al proyecto, que es sólo uno de los tres
    caminos a una tarea (el tablero de Tareas, la lista y Mandados son los
    otros). Ahora la ruta de vuelta la decide el recorrido de verdad; el proyecto
    queda como el default de siempre para quien llega sin rastro (un enlace
    pegado, un marcador).
    """
    origen = _rastro_util(request)
    for prefijo, etiqueta, nombre_url in _ORIGENES_TAREA:
        if origen.startswith(prefijo):
            return {
                "breadcrumb_items": [
                    {"url": reverse(nombre_url), "label": etiqueta},
                    {"label": tarea.titulo},
                ],
                # Se regresa a la URL EXACTA de donde vino, no al índice: así no
                # se pierden los filtros ni la columna en la que estaba.
                "back_url": origen,
                "back_label": etiqueta,
                "volver_url": origen,
                "volver_label": etiqueta,
            }

    proyecto_url = reverse("proyectos-detalle", args=[tarea.proyecto_id])
    return {
        "breadcrumb_items": [
            {"url": reverse("proyectos-kanban"), "label": "Proyectos"},
            {"url": proyecto_url, "label": tarea.proyecto.codigo},
            {"label": tarea.titulo},
        ],
        "back_url": proyecto_url,
        "back_label": tarea.proyecto.codigo,
        "volver_url": proyecto_url,
        "volver_label": "Proyecto",
    }


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
    # LC Fase 2: el default ahora es TODAS las tareas vigentes del despacho (sin
    # preseleccionar "mis tareas"). El usuario filtra a sí mismo con el chip de
    # persona si quiere. (Los runner-only siguen acotados abajo a sus mandados.)

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

    # Oscar (2026-08-23): «cuando seleccionas los mandados, saca el tablero de
    # mandados de ahí, que se vea en tareas». Antes había un enlace que te sacaba
    # de la página; ahora el tablero de reparto se pinta aquí mismo. Sus chips
    # filtran con `m_estado` para no pisar el `estado` de las tareas.
    tablero_mandados = None
    if cat == "mandados":
        tablero_mandados = _ctx_tablero_mandados(
            request,
            base=_qs_filtros(estados_sel, personas_sel, "mandados"),
            param="m_estado",
        )

    return render(request, "pizarron/kanban.html", {
        "tablero_mandados": tablero_mandados,
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
    el Dashboard y la página Tareas. Proyecto/persona/tipo con un click.

    Revisión buzón R2: si la petición es HTMX se sirve como **form-in-modal**
    (render de Oscar) en el #modal-slot; POST HTMX → 204 + HX-Redirect. La
    página full se conserva como fallback (navegación directa a la URL)."""
    TERMINALES_PRY = {"entregado", "cerrado", "cancelado"}
    es_htmx = request.headers.get("HX-Request") == "true"
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
            if es_htmx:
                from django.http import HttpResponse
                from django.urls import reverse
                return HttpResponse(status=204, headers={"HX-Redirect": reverse("tareas-kanban")})
            return redirect("tareas-kanban")
        # inválido → cae al render de abajo (con errores). Modal si es HTMX.
    else:
        # Fecha precargada desde el Calendario (?fecha=YYYY-MM-DD). LC 2026-06-29.
        initial = {}
        f = request.GET.get("fecha")
        if f:
            initial["fecha_compromiso"] = f
        form = TareaGlobalForm(initial=initial)
    from cuentas.models.usuario import Usuario
    proyectos_mgr = getattr(Proyecto, "activos", Proyecto.objects)
    proyectos_activos = (
        proyectos_mgr.exclude(estado__in=TERMINALES_PRY)
        .select_related("cliente").order_by("-creado_en")
    )
    proyectos_chips = list(proyectos_activos[:60])
    ctx = {
        "form": form,
        "proyectos_chips": proyectos_chips,
        "usuarios_chips": list(Usuario.objects.filter(is_active=True).order_by("nombre_completo")),
        "tipos_chips": Tarea._meta.get_field("tipo").choices,
    }
    if es_htmx:
        # Prepara el form para el modal (render de Oscar): combobox buscable en
        # Proyecto/Asignar a + placeholder del título.
        form.fields["titulo"].widget.attrs["placeholder"] = "¿Qué hay que hacer?"
        form.fields["proyecto"].queryset = proyectos_activos
        form.fields["proyecto"].empty_label = "— Elige un proyecto —"
        for campo in ("proyecto", "asignada_a"):
            form.fields[campo].widget.attrs["data-select-buscable"] = "1"
        return render(request, "pizarron/_modal_nueva_tarea.html", ctx)
    return render(request, "pizarron/form_tarea_global.html", ctx)


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
        **_navegacion_tarea(request, tarea),
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
    # Archivado inline desde la tabla de tareas del proyecto (ticket UX 2026-07):
    # HTMX → respuesta vacía para que la fila (hx-target) desaparezca sin recargar.
    if request.headers.get("HX-Request") == "true":
        from django.http import HttpResponse
        return HttpResponse("")
    messages.success(
        request,
        f"Tarea «{tarea.titulo[:60]}» {'archivada' if tarea.archivada else 'desarchivada'}.")
    destino = request.POST.get("next") or reverse("tareas-kanban")
    return redirect(destino)


@login_required
def reordenar_tareas(request):
    """LC 2026-08-07 (Oscar): persiste el acomodo manual de las tablas de tareas.

    Recibe `orden` = lista de pks en el nuevo orden de UNA tabla (la del proyecto
    o la lista general). Es compartido: lo que uno acomoda lo ve el equipo, igual
    que el Kanban de Proyectos. Sólo escribe `orden`, así que no toca estados,
    fechas ni responsables. Idempotente y acotado a las tareas que el usuario
    puede ver — un pk ajeno se ignora en silencio.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    crudos = request.POST.getlist("orden")
    pks = []
    for crudo in crudos:
        try:
            pks.append(int(crudo))
        except (TypeError, ValueError):
            continue
    if not pks:
        return HttpResponse(status=204)
    visibles = set(
        _tareas_visibles(request.user).filter(pk__in=pks).values_list("pk", flat=True)
    )
    for indice, tarea_pk in enumerate(pks):
        if tarea_pk in visibles:
            Tarea.objects.filter(pk=tarea_pk).update(orden=indice)
    return HttpResponse(status=204)


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
            # El rastro sobrevive al guardado: si venías de Tareas, el detalle al
            # que caes también sabe regresar a Tareas.
            destino = reverse("pizarron-detalle-tarea", args=[tarea.pk])
            rastro = _rastro_util(request)
            if rastro:
                from urllib.parse import quote
                destino = f"{destino}?volver={quote(rastro, safe='')}"
            return redirect(destino)
    else:
        form = TareaForm(instance=tarea)
    return render(request, "pizarron/form_tarea.html", {
        "form": form, "tarea": tarea, "proyecto": tarea.proyecto, "modo": "editar",
        "volver": _rastro_util(request),
    })


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

def _ctx_tablero_mandados(request, *, base: str, param: str = "estado") -> dict:
    """Contexto del tablero de reparto, para quien lo quiera mostrar.

    Lo usan DOS pantallas: `/mandados/` y Tareas cuando se filtra por la
    categoría Mandados. Vive en un solo lugar para que no se separen.

    `base` y `param` son de quien lo muestra: así los chips filtran **sin sacar a
    nadie de su página**. En Tareas el parámetro es `m_estado`, porque `estado`
    ya lo usa el filtro de estado de las tareas y se pisarían.
    """
    from apps.el_pizarron.mandados import mandados_visibles
    from apps.el_pizarron.models.mandado import ESTADOS_MANDADO

    qs = mandados_visibles(request.user)
    validos = {s for s, _, _ in ESTADOS_MANDADO}
    sel = request.GET.get(param, "")
    if sel in validos:
        qs = qs.filter(estado=sel)

    mandados = list(
        qs.order_by("estado", "tarea__fecha_compromiso", "-creado_en")[:300]
    )

    sep = "&" if "?" in base else "?"
    chips = [{"slug": "", "label": "Todos", "url": base, "activo": sel == ""}]
    for slug, label, color in ESTADOS_MANDADO:
        chips.append({
            "slug": slug, "label": label, "color": color,
            "url": f"{base}{sep}{param}={slug}", "activo": sel == slug,
        })

    return {
        "mandados": mandados,
        "chips": chips,
        "total": len(mandados),
        "puede_admin": es_admin(request.user),
    }


def mandados_lista(request):
    """Lista propia de El Runner: entregas/recolecciones como entidad logística,
    filtrables por estado de reparto. Cada fila enlaza a su proyecto y permite
    avanzar el estado o fijar el destino (pin)."""
    return render(request, "mandados/lista.html", _ctx_tablero_mandados(
        request, base=reverse("mandados-lista"),
    ))


@login_required
def mi_ruta(request):
    """La vuelta de hoy: los mandados abiertos del runner, en orden de cercanía.

    El orden se calcula empezando por donde está (su última checada) y saltando
    cada vez a la parada más próxima. Los botones abren la ruta ya armada en
    Waze, Google Maps o Apple Maps — sin servicios de paga: son enlaces.
    """
    from apps.el_pizarron.ruta import ruta_de

    # Si alguien ya le planeó la ruta, ÉSA es su ruta: trae el orden que decidió
    # una persona y las citas respetadas. El cálculo al vuelo queda de respaldo
    # para el runner que salió sin plan.
    datos = _mi_ruta_planeada(request.user) or ruta_de(request.user)
    return render(request, "mandados/mi_ruta.html", {
        **datos,
        "titulo_pagina": "Mi ruta de hoy",
    })


def _mi_ruta_planeada(usuario) -> dict | None:
    """La ruta guardada de hoy, en la MISMA forma que `ruta.ruta_de`.

    Devolver la misma forma es lo que permite que la pantalla no tenga que saber
    de dónde salió la ruta.
    """
    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS, Ruta
    from apps.el_pizarron.planeador import enlaces_de

    ruta = (
        Ruta.objects.filter(
            fecha=timezone.localdate(), runner=usuario,
            estado__in=ESTADOS_RUTA_VIVOS,
        )
        .prefetch_related("paradas__mandado__tarea__proyecto__cliente")
        .first()
    )
    if ruta is None or not ruta.paradas.exists():
        return None

    paradas = []
    for parada in ruta.paradas.all():
        tarea = parada.mandado.tarea
        proyecto = getattr(tarea, "proyecto", None)
        cliente = getattr(proyecto, "cliente", None)
        paradas.append({
            "id": parada.mandado_id,
            "titulo": tarea.titulo,
            "lugar": parada.etiqueta,
            "cliente": cliente.razon_social if cliente is not None else "",
            "lat": parada.lat, "lng": parada.lng,
            "estado": parada.mandado.estado,
            "cita": parada.hora_cita,
            "llegada": parada.llegada_estimada,
        })
    enlaces = enlaces_de(ruta)
    return {
        "paradas": paradas,
        "origen": ruta.origen_punto,
        "total_km": ruta.distancia_km or None,
        "sin_ubicar": sum(1 for p in paradas if p["lat"] is None),
        "url_google": enlaces["google"],
        "url_apple": enlaces["apple"],
        "url_waze": enlaces["waze"],
        "planeada": True,
        "ruta": ruta,
    }


def _coordenadas_del_post(request):
    """Lee lat/lng del POST si vienen y son números creíbles.

    Mismo criterio que El Checador: la ubicación nunca bloquea la acción. Un
    valor fuera de rango se descarta en silencio en vez de guardarse mal.
    """
    try:
        lat = float(request.POST.get("lat"))
        lng = float(request.POST.get("lng"))
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


@login_required
def mandado_avanzar(request, pk):
    """POST: avanza el estado de reparto (en_camino | entregado | cancelar)."""
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    from apps.el_pizarron import mandados as svc
    m = _mandado_visible_o_404(request, pk)
    accion = (request.POST.get("accion") or "").strip()
    # Dónde está el runner al picar el botón. El teléfono la manda si puede; si
    # no, se avanza igual (2026-08-22 — sirve para medir tiempos y distancia).
    lat, lng = _coordenadas_del_post(request)
    evento = None
    try:
        if accion == "en_camino":
            svc.marcar_en_camino(m, lat=lat, lng=lng)
            evento = "en_camino"
            messages.success(request, "Mandado marcado en camino.")
        elif accion == "entregado":
            svc.marcar_entregado(m, lat=lat, lng=lng)
            evento = "entregado"
            recorrido = m.km_recorridos
            minutos = m.minutos_en_ruta
            detalle = ""
            if minutos is not None:
                detalle = f" {minutos} min"
                if recorrido:
                    detalle += f" · {recorrido} km"
            messages.success(request, f"Mandado entregado. ✅{detalle}")
        elif accion == "cancelar":
            svc.cancelar(m, motivo=(request.POST.get("motivo") or "").strip())
            evento = "cancelado"
            messages.success(request, "Mandado cancelado.")
        elif accion == "reactivar":
            # La salida que no existía: `sincronizar_mandado` respeta la
            # cancelación para siempre, así que un mandado cancelado por error
            # dejaba la tarea Pendiente y la entrega sin salir, sin aviso.
            svc.reactivar(m)
            evento = "reactivado"
            messages.success(
                request,
                "Reparto reactivado: la entrega vuelve a entrar al planeador.",
            )
        else:
            messages.error(request, "Acción no válida.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if evento:
        # Push a los involucrados (quien lo mandó, asignado, runner) — A8.
        svc.notificar_involucrados(m, evento, actor=request.user)
        _emitir_mandado("mandado.estado_cambiado", request.user, m, {"accion": accion})
    # A dónde regresa lo decide el recorrido: este botón también vive en el
    # panel de rutas, y mandar de ahí a la lista de Mandados saca al usuario de
    # donde estaba trabajando (`lib.navegacion`, contrato único de «volver»).
    from lib.navegacion import destino_de_regreso
    return redirect(destino_de_regreso(request, reverse("mandados-lista")))


#: A cuántos metros de una calle deja de ser creíble un pin. Cien metros es
#: media manzana: más que eso y el runner llega a un punto sin acceso.
_METROS_PIN_SOSPECHOSO = 100


def _avisar_si_el_pin_quedo_lejos(request, lat, lng) -> None:
    """Avisa —nunca bloquea— si el punto cayó lejos de cualquier calle.

    La ubicación jamás detiene una acción en este repo; lo único que se hace es
    decirlo, porque un pin en medio de una manzana manda al runner a un lugar
    al que no se puede llegar en coche.
    """
    if lat is None or lng is None:
        return
    try:
        from lib import ruteo
        cerca = ruteo.cerca_de_calle(lat, lng)
    except Exception:  # noqa: BLE001 — un aviso no puede tumbar el guardado
        return
    if not cerca or cerca["metros"] <= _METROS_PIN_SOSPECHOSO:
        return
    calle = f" (la más cercana es {cerca['calle']})" if cerca["calle"] else ""
    messages.warning(
        request,
        f"Ojo: el punto quedó a {cerca['metros']:.0f} m de la calle más "
        f"cercana{calle}. Se guardó igual, pero revisa que el runner pueda "
        "llegar ahí.",
    )


@login_required
def mandado_destino(request, pk):
    """Fija el destino (pin Leaflet). GET (HTMX) → modal con mapa; POST → guarda
    lat/lng/etiqueta en la Tarea subyacente."""
    from apps.el_pizarron import mandados as svc

    from lib.navegacion import destino_de_regreso
    m = _mandado_visible_o_404(request, pk)
    # Fijar el destino se pide desde la lista de Mandados Y desde el planeador:
    # regresar siempre a la lista sacaba de la pantalla a quien venía del otro.
    volver = destino_de_regreso(request, reverse("mandados-lista"))

    if request.method == "POST":
        # El pin es OPCIONAL: una dirección escrita ya sirve, y perder lo que la
        # persona escribió por no haber picado el mapa era el bug que reportó
        # Oscar. Si no hay coordenadas, se guarda la dirección igual.
        lat = lng = None
        try:
            lat = float(request.POST.get("lat"))
            lng = float(request.POST.get("lng"))
        except (TypeError, ValueError):
            lat = lng = None
        etiqueta = (request.POST.get("etiqueta") or "").strip()

        if lat is None and not etiqueta:
            # Sin nada que guardar, el fallo tiene que VERSE: con hx-swap="none"
            # un redirect no se nota y parecía que había guardado.
            error = "Escribe una dirección o pica un punto en el mapa."
            if request.headers.get("HX-Request") == "true":
                return render(request, "mandados/_modal_destino.html",
                              {"m": m, "error": error, "volver": volver})
            messages.error(request, error)
            return redirect(volver)

        svc.fijar_destino(m, lat=lat, lng=lng, etiqueta=etiqueta)
        _emitir_mandado("mandado.destino_fijado", request.user, m,
                        {"lat": lat, "lng": lng, "con_pin": lat is not None})
        _avisar_si_el_pin_quedo_lejos(request, lat, lng)
        if request.headers.get("HX-Request") == "true":
            from django.http import HttpResponse
            return HttpResponse(status=204, headers={"HX-Redirect": volver})
        messages.success(request, "Destino del mandado actualizado.")
        return redirect(volver)

    # Los POIs ya no se precargan: el geo-picker los trae en vivo desde
    # /geo/buscar conforme el usuario escribe (cuadro de resultados).
    return render(request, "mandados/_modal_destino.html", {"m": m, "volver": volver})


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
    filtro = q_texto(q, "razon_social", "direccion", "direccion_fiscal")
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


# ── El planeador de rutas (S-Planeador-Rutas) ────────────────────────────────

def _sedes_con_pin():
    from apps.checador.models.sede import SedeLC
    return list(SedeLC.objects.filter(activa=True, lat__isnull=False, lng__isnull=False))


def _fecha_de(request):
    """La fecha que se está planeando. Un texto raro cae a hoy, no a un 500."""
    import datetime as dt
    texto = (request.GET.get("fecha") or request.POST.get("fecha") or "").strip()
    try:
        return dt.date.fromisoformat(texto) if texto else timezone.localdate()
    except ValueError:
        return timezone.localdate()


def _rutas_del_dia(request, fecha):
    """Las rutas que este usuario puede ver ese día.

    Quien planea ve todas; un runner ve sólo la suya — la vuelta de un compañero
    no es asunto suyo.
    """
    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS, Ruta

    from lib.permisos import puede_planear_rutas

    qs = (
        Ruta.objects.filter(fecha=fecha, estado__in=ESTADOS_RUTA_VIVOS)
        .select_related("runner", "sede")
        .prefetch_related(
            "paradas__mandado__tarea__proyecto__cliente",
            "paradas__mandado__tarea__runner",
        )
    )
    if not puede_planear_rutas(request.user):
        qs = qs.filter(runner=request.user)
    return list(qs)


@login_required
def rutas_panel(request):
    """El planeador: las rutas del día, el mapa y lo que quedó sin repartir."""
    from apps.el_pizarron.models.ruta import COLORES_RUTA_MAPA
    from apps.el_pizarron.planeador import (
        enlaces_de,
        paradas_con_dueno_ajeno,
        sueltos_del_dia,
    )

    from lib.permisos import (
        puede_despachar_rutas,
        puede_planear_rutas,
        puede_ver_rutas,
    )

    if not puede_ver_rutas(request.user):
        return HttpResponseForbidden("Sin permiso para ver las rutas.")

    fecha = _fecha_de(request)
    rutas = _rutas_del_dia(request, fecha)

    tarjetas = []
    for i, ruta in enumerate(rutas):
        tarjetas.append({
            "ruta": ruta,
            "color": COLORES_RUTA_MAPA[i % len(COLORES_RUTA_MAPA)],
            "enlaces": enlaces_de(ruta),
            "paradas": list(ruta.paradas.all()),
        })

    # Lo que todavía no está en una ruta, separado por la razón REAL: uno se
    # arregla apretando «Planear el día» y el otro poniéndole el destino. Antes
    # iban juntos bajo «no se sabe a dónde van», así que un mandado con su
    # destino puesto salía acusado de no tenerlo.
    sueltos = (
        sueltos_del_dia(fecha) if puede_planear_rutas(request.user)
        else {"con_destino": [], "sin_destino": [], "cancelados": []}
    )

    # El descuadre se muestra ANTES de picar nada: la ruta se ve perfectamente
    # bien en la pantalla mientras el mandado dice que es de otra persona, y
    # nadie va a apretar «Planear el día» para arreglar algo que no sabe que
    # está roto. Al planear se endereza y se dice qué se movió.
    descuadres = [
        {"parada": parada, "dueno": dueno,
         "ya_despachada": parada.ruta.estado != "borrador"}
        for parada, dueno in (
            paradas_con_dueno_ajeno(fecha) if puede_planear_rutas(request.user)
            else []
        )
    ]

    return render(request, "mandados/rutas_panel.html", {
        "titulo_pagina": "Planeador de rutas",
        "fecha": fecha,
        "tarjetas": tarjetas,
        "por_repartir": sueltos["con_destino"],
        "sin_destino": sueltos["sin_destino"],
        "cancelados": sueltos["cancelados"],
        "descuadres": descuadres,
        "sedes": _sedes_con_pin(),
        "puede_planear": puede_planear_rutas(request.user),
        "puede_despachar": puede_despachar_rutas(request.user),
        "mapa": _mapa_de(tarjetas),
    })


def _trazo_por_calles(coords):
    """El recorrido dibujado por las calles, o las líneas rectas de siempre.

    Sin esto el mapa une los pines con una regla, que es una forma bonita de
    mentir sobre por dónde va a pasar el runner. Best-effort: si el mapa no
    contesta, se devuelven los mismos puntos y el mapa se ve como antes.
    """
    if len(coords) < 2:
        return coords
    try:
        from lib import ruteo
        calles = ruteo.trazo([(lat, lng) for lat, lng in coords])
    except Exception:  # noqa: BLE001 — dibujar de más nunca tumba la pantalla
        return coords
    return calles or coords


def _mapa_de(tarjetas) -> dict:
    """Datos para Leaflet: una línea por ruta, con su color y sus pines."""
    lineas, puntos = [], []
    for t in tarjetas:
        ruta = t["ruta"]
        coords = []
        if ruta.tiene_origen:
            coords.append([ruta.origen_lat, ruta.origen_lng])
        for parada in t["paradas"]:
            if parada.lat is None or parada.lng is None:
                continue
            coords.append([parada.lat, parada.lng])
            puntos.append({
                "lat": parada.lat, "lng": parada.lng, "color": t["color"],
                "etiqueta": f"{parada.orden}. {parada.etiqueta}",
            })
        if ruta.es_redonda and ruta.tiene_origen and len(coords) > 1:
            coords.append([ruta.origen_lat, ruta.origen_lng])
        if len(coords) > 1:
            lineas.append({"color": t["color"], "coords": _trazo_por_calles(coords),
                           "runner": ruta.runner.nombre_completo})
    return {"lineas": lineas, "puntos": puntos}


@login_required
def rutas_planear(request):
    """POST: arma (o rearma) el reparto del día."""
    from apps.el_pizarron.planeador import planear_dia

    from lib.permisos import puede_planear_rutas

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not puede_planear_rutas(request.user):
        return HttpResponseForbidden("Sin permiso para planear rutas.")

    fecha = _fecha_de(request)
    modo = request.POST.get("origen_modo") or "sede_redonda"
    if modo not in ("sede_redonda", "runner_abierta"):
        modo = "sede_redonda"

    sede = None
    sede_pk = (request.POST.get("sede") or "").strip()
    if sede_pk.isdigit():
        from apps.checador.models.sede import SedeLC
        sede = SedeLC.objects.filter(pk=int(sede_pk), activa=True).first()
    if modo == "sede_redonda" and sede is None:
        sedes = _sedes_con_pin()
        sede = sedes[0] if sedes else None

    # «Rehacer» tira los BORRADORES del día y arma el reparto de cero. Sin esto,
    # un reparto que salió mal no se podía corregir: `candidatos_del_dia` excluye
    # a propósito lo que ya está ruteado, así que replanear sólo agregaba.
    rehacer = request.POST.get("rehacer") == "1"
    res = planear_dia(fecha, origen_modo=modo, sede=sede, actor=request.user,
                      rehacer=rehacer)

    # Lo primero que se dice es lo que se MOVIÓ, porque cambia la vuelta de
    # alguien más. Si esa ruta ya estaba despachada, esa persona recibió el
    # correo con una entrega que ya no es suya y eso sólo se arregla avisándole:
    # el mensaje la nombra en vez de dejarlo pasar.
    for m in res.get("reconciliadas") or []:
        aviso = (
            f"«{m['titulo']}» volvió con {m['a'].nombre_completo}, que es quien "
            f"la trae asignada: estaba en la ruta de {m['de'].nombre_completo}."
        )
        if m["ya_despachada"]:
            aviso += (
                f" Esa ruta ya estaba despachada, así que a "
                f"{m['de'].nombre_completo} le llegó por correo: avísale."
            )
        messages.warning(request, aviso)

    if res["sin_runner"]:
        messages.warning(
            request,
            "Nadie tiene el permiso de recibir mandados: asigna el rol «Runner» "
            "en El Directorio y vuelve a planear.",
        )
    else:
        paradas = sum(r.total_paradas for r in res["rutas"])
        messages.success(
            request,
            f"Listo: {paradas} parada{'s' if paradas != 1 else ''} en "
            f"{len(res['rutas'])} ruta{'s' if len(res['rutas']) != 1 else ''}.",
        )
        if res["sin_ubicar"]:
            messages.warning(
                request,
                f"{len(res['sin_ubicar'])} entrega(s) quedaron fuera porque no se "
                "sabe a dónde van: fíjale el destino en el mapa del mandado.",
            )
        if res["sobrantes"]:
            # Se describe el HECHO, no la causa. El tope de paradas es la razón
            # habitual, pero no la única (si nadie es elegible, tampoco entran) y
            # afirmar una causa equivocada es el bug que este sprint vino a
            # arreglar. El aviso de `sin_permiso` explica el otro caso.
            messages.warning(
                request,
                f"{len(res['sobrantes'])} entrega(s) no entraron a ninguna ruta. "
                "Lo más común es que las rutas llegaran a su tope de paradas.",
            )
        if res.get("sin_permiso"):
            # Se le respetó su mandado (manda quien ya lo trae), pero conviene
            # saberlo: el reparto automático nunca le va a dar trabajo nuevo.
            nombres = ", ".join(u.nombre_completo for u in res["sin_permiso"])
            messages.warning(
                request,
                f"{nombres} trae mandados y armé su ruta, pero no tiene el permiso "
                "de recibir mandados: el reparto automático no le puede asignar "
                "nada nuevo. Dale el rol «Runner» en El Directorio.",
            )
    return redirect(f"{reverse('rutas-panel')}?fecha={fecha.isoformat()}")


def _ruta_o_403(request, pk, *, para_despachar: bool = False):
    """La ruta, si esta persona la puede tocar. None si no."""
    from apps.el_pizarron.models.ruta import Ruta

    from lib.permisos import puede_despachar_rutas, puede_planear_rutas

    ruta = get_object_or_404(Ruta, pk=pk)
    permitido = (
        puede_despachar_rutas(request.user) if para_despachar
        else puede_planear_rutas(request.user)
    )
    return ruta if permitido else None


@login_required
def rutas_despachar(request, pk):
    """POST: publica la ruta — y con eso le llega el correo al runner."""
    from apps.el_pizarron.planeador import despachar

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    ruta = _ruta_o_403(request, pk, para_despachar=True)
    if ruta is None:
        return HttpResponseForbidden("Sin permiso para despachar rutas.")
    try:
        despachar(ruta, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(
            request,
            f"Ruta despachada. Se le mandó a {ruta.runner.nombre_completo} "
            "por correo." if ruta.correo_enviado_en else
            "Ruta despachada. El correo no salió — revisa Ajustes → Cartero.",
        )
    return redirect(f"{reverse('rutas-panel')}?fecha={ruta.fecha.isoformat()}")


@login_required
def rutas_reordenar(request, pk):
    """POST del arrastre: el orden que dejó la persona manda."""
    from apps.el_pizarron.planeador import reordenar

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    ruta = _ruta_o_403(request, pk)
    if ruta is None:
        return HttpResponseForbidden("Sin permiso.")
    pks = [p for p in request.POST.getlist("orden") if str(p).isdigit()]
    reordenar(ruta, pks)
    return HttpResponse(status=204)


@login_required
def parada_mover(request, pk):
    """POST del arrastre entre runners: pasa una parada a otra ruta."""
    from apps.el_pizarron.models.ruta import ParadaRuta, Ruta
    from apps.el_pizarron.planeador import mover_parada

    from lib.permisos import puede_planear_rutas

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not puede_planear_rutas(request.user):
        return HttpResponseForbidden("Sin permiso.")
    parada = get_object_or_404(ParadaRuta, pk=pk)
    destino_pk = (request.POST.get("ruta") or "").strip()
    if not destino_pk.isdigit():
        return HttpResponseForbidden("Falta la ruta de destino.")
    destino = get_object_or_404(Ruta, pk=int(destino_pk))
    mover_parada(parada, destino)
    return HttpResponse(status=204)


@login_required
def parada_indicaciones(request, pk):
    """GET (HTMX): cómo llegar a esta parada, giro por giro y en español.

    El punto de partida es la parada anterior de la misma ruta; si es la
    primera, el origen de la vuelta. Quien maneja puede verlas aunque no pueda
    planear — es su ruta.
    """
    from apps.el_pizarron.models.ruta import ParadaRuta

    from lib.permisos import puede_planear_rutas, puede_ver_rutas

    if not puede_ver_rutas(request.user):
        return HttpResponseForbidden("Sin permiso para ver las rutas.")
    parada = get_object_or_404(
        ParadaRuta.objects.select_related("ruta", "ruta__runner", "mandado__tarea"),
        pk=pk,
    )
    # Un runner ve la suya; quien planea, todas.
    if (parada.ruta.runner_id != request.user.pk
            and not puede_planear_rutas(request.user)):
        return HttpResponseForbidden("Esa ruta no es tuya.")

    anteriores = list(
        parada.ruta.paradas.filter(orden__lt=parada.orden).order_by("-orden")[:1]
    )
    desde = anteriores[0].punto if anteriores else parada.ruta.origen_punto
    etiqueta_desde = (
        anteriores[0].etiqueta if anteriores else parada.ruta.origen_etiqueta
    )

    datos = None
    if desde and parada.punto:
        from lib import ruteo
        datos = ruteo.indicaciones(desde, parada.punto)

    return render(request, "mandados/_modal_indicaciones.html", {
        "parada": parada,
        "desde": etiqueta_desde or "el punto de partida",
        "datos": datos,
    })


@login_required
def rutas_cancelar(request, pk):
    """POST: cancela la ruta (deja de estorbar para volver a planear el día)."""
    from apps.el_pizarron.planeador import cancelar

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    ruta = _ruta_o_403(request, pk)
    if ruta is None:
        return HttpResponseForbidden("Sin permiso.")
    cancelar(ruta, motivo=sanear_contexto(request.POST.get("motivo", ""))[:200])
    messages.success(request, "Ruta cancelada.")
    return redirect(f"{reverse('rutas-panel')}?fecha={ruta.fecha.isoformat()}")
