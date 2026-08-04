from apps.la_cartera.forms import (
    ClienteContactoFormSet,
    ClienteForm,
    ClienteRazonSocialFormSet,
)
from apps.la_cartera.models import Cliente
from apps.la_cartera.models.cliente import ESTADOS_CLIENTE
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_http_methods

from lib.permisos import (
    puede_editar_cartera,
    puede_eliminar_cartera,
    puede_ver_cartera,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _gate(request, ver=True):
    if ver and not puede_ver_cartera(request.user):
        return HttpResponseForbidden("Sin acceso a Clientes.")
    return None


# Estados de proyecto que cuentan como "activo en taller" (alineado con kpis.py).
ESTADOS_PROYECTO_ACTIVOS = ("en_proceso_diseno", "en_proceso_produccion")


def _buscar_clientes(qs, q):
    from django.db.models import Q
    return qs.filter(
        Q(razon_social__icontains=q)
        | Q(razon_social_fiscal__icontains=q)
        | Q(rfc__icontains=q)
        # LC 2026-07-26: y por CUALQUIERA de sus razones sociales de facturación.
        | Q(razones_sociales__razon_social__icontains=q)
        | Q(razones_sociales__rfc__icontains=q)
        | Q(email_contacto__icontains=q)
        | Q(nombre_contacto__icontains=q)
        | Q(contactos__nombre__icontains=q)
        | Q(contactos__email__icontains=q)
        | Q(proyectos__nombre__icontains=q)
        | Q(proyectos__codigo__icontains=q)
    ).distinct()


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    from django.db.models import Count

    q = (request.GET.get("q") or "").strip()
    # Vista/filtro: nombre (default) · contacto · activos · con_proyectos · prospectos.
    ver = (request.GET.get("ver") or "nombre").strip()
    if ver not in {"nombre", "contacto", "activos", "con_proyectos", "prospectos"}:
        ver = "nombre"

    # Edición rápida (mismo patrón que Productos): opt-in por ?editar=1 y gated
    # por permiso. En este modo cada celda autoguarda vía hx-post a la celda.
    puede_editar = puede_editar_cartera(request.user)
    editar_inline = request.GET.get("editar") == "1" and puede_editar

    def _anota(qs):
        return qs.annotate(num_proyectos=Count("proyectos", distinct=True))

    # Al buscar, se busca en TODOS (incluso archivados) y se muestra el estado.
    base = Cliente.objects.all() if q else Cliente.activos.all()
    qs = _anota(base.select_related())
    if q:
        qs = _buscar_clientes(qs, q)

    if ver == "activos":
        qs = qs.filter(estado="activo")
    elif ver == "prospectos":
        qs = qs.filter(estado="prospecto")
    elif ver == "con_proyectos":
        qs = qs.filter(proyectos__estado__in=ESTADOS_PROYECTO_ACTIVOS).distinct()

    qs = qs.order_by("nombre_contacto", "razon_social") if ver == "contacto" else qs.order_by("razon_social", "pk")

    # LC Fase 1 (2026-07, decisión Oscar): sin paginación — mostramos TODOS los
    # clientes en una sola página. El padrón de Learning Center es acotado y ver
    # el listado completo de un vistazo pesa más que segmentar por páginas.
    clientes = list(qs)

    # Clientes archivados — sección desplegable (solo cuando NO se busca).
    archivados_lista = []
    if not q:
        archivados_lista = list(_anota(Cliente.objects.filter(activo=False)).order_by("razon_social"))

    # KPIs hero (3): con proyectos activos · activos · archivados.
    activos = Cliente.activos.count()
    archivados = Cliente.objects.filter(activo=False).count()
    con_proyectos_activos = Cliente.activos.filter(
        proyectos__estado__in=ESTADOS_PROYECTO_ACTIVOS
    ).distinct().count()

    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if ver != "nombre":
        qs_filtros.append(f"ver={ver}")
    return render(request, "cartera/lista.html", {
        "clientes": clientes,
        "page_obj": None,
        "q": q,
        "ver_actual": ver,
        "archivados_lista": archivados_lista,
        "querystring_base": "&".join(qs_filtros),
        "querystring_paginacion": "&".join(qs_filtros),
        "puede_editar": puede_editar,
        "puede_eliminar": puede_eliminar_cartera(request.user),
        "editar_inline": editar_inline,
        "estados_cliente": ESTADOS_CLIENTE,
        "kpi_activo_con_proyectos": ver == "con_proyectos",
        "kpi_activo_activos": ver == "activos",
        "ver_opciones": [
            ("nombre", "Nombre A-Z"),
            ("contacto", "Contacto A-Z"),
            ("activos", "Activos"),
            ("con_proyectos", "Con proyectos"),
            ("prospectos", "Prospectos"),
        ],
        "kpis": {
            "activos": activos,
            "archivados": archivados,
            "con_proyectos": con_proyectos_activos,
        },
    })


def _ligado_del_cliente(cliente) -> dict:
    """TODO lo que el cliente tiene ligado (LC 2026-07-25, Oscar).

    Sirve para dos cosas: (a) mostrarlo en su ficha —cotizaciones, facturas e
    ingresos, que antes no se veían en ningún lado— y (b) explicar con precisión
    qué impide su borrado permanente. Los tres modelos apuntan al cliente con FK
    PROTECT (proyectos, facturas, cotizaciones), así que cualquier fila —incluso
    anulada o cancelada— bloquea el `delete()`; por eso el aviso las enlista.
    """
    from apps.cotizaciones.models import Cotizacion
    from apps.facturacion.models import Factura
    from apps.tesoreria.models import Ingreso

    proyectos = list(
        cliente.proyectos.all().only("pk", "codigo", "nombre", "estado").order_by("-pk")
    )
    cotizaciones = list(
        Cotizacion.objects.filter(cliente=cliente)
        .select_related("proyecto").order_by("-pk")
    )
    facturas = list(
        Factura.objects.filter(cliente=cliente)
        .select_related("proyecto").order_by("-pk")
    )
    ingresos = list(
        Ingreso.objects.filter(cliente=cliente)
        .select_related("proyecto").order_by("-fecha", "-pk")
    )
    return {
        "proyectos": proyectos,
        "cotizaciones": cotizaciones,
        "facturas": facturas,
        "ingresos": ingresos,
        # Lo que impide el borrado permanente (FK PROTECT). Los ingresos son
        # SET_NULL, así que NO bloquean.
        "bloqueos": (
            [{"tipo": "Proyecto", "etiqueta": f"{p.nombre or p.codigo} ({p.codigo})",
              "url": reverse("proyectos-detalle", args=[p.pk])} for p in proyectos]
            + [{"tipo": "Factura", "etiqueta": f"{f.folio or f.codigo} · {f.get_estado_display()}",
                "url": reverse("facturacion:detalle", args=[f.pk])} for f in facturas]
            + [{"tipo": "Cotización", "etiqueta": f"{c.codigo} · {c.get_estado_display()}",
                "url": reverse("cotizaciones:detalle", args=[c.pk])} for c in cotizaciones]
        ),
    }


@login_required
def detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    from decimal import Decimal

    from apps.los_proyectos.models.estado import EstadoProyecto
    cliente = get_object_or_404(Cliente, pk=pk)
    puede_editar = puede_editar_cartera(request.user)

    # Proyectos agrupados por estado, ordenados por el orden del estado
    # (los activos del flujo quedan arriba; terminales abajo).
    proyectos = list(cliente.proyectos.all())
    orden_estados = {e.slug: e.orden for e in EstadoProyecto.objects.all()}
    grupos: dict[str, list] = {}
    for p in proyectos:
        grupos.setdefault(p.estado, []).append(p)
    proyectos_por_estado = [
        {"slug": slug, "proyectos": ps}
        for slug, ps in sorted(grupos.items(), key=lambda kv: orden_estados.get(kv[0], 999))
    ]

    # Header cards del cliente.
    TERMINALES = {"entregado", "cerrado", "cancelado"}
    proyectos_activos = [p for p in proyectos if p.estado not in TERMINALES]
    por_cobrar = sum(
        (max(Decimal("0"), (p.monto_facturado or Decimal("0")) - (p.monto_cobrado or Decimal("0")))
         for p in proyectos_activos),
        Decimal("0"),
    )
    kpis_cliente = {
        "proyectos_activos": len(proyectos_activos),
        "proyectos_totales": len(proyectos),
        "conversion": "—",  # placeholder — se define con LC más adelante
        "por_cobrar": por_cobrar,
    }

    action_bar_meta = format_html(
        '<span>Última actualización <time class="text-gray-700 dark:text-gray-200">{}</time></span>',
        cliente.actualizado_en.strftime("%d %b %Y %H:%M"),
    )
    action_bar_acciones = ""
    if puede_editar:
        action_bar_acciones = format_html(
            '<a href="{}" class="btn-secundario">Editar</a>'
            '<button type="button" class="btn-destructivo" hx-get="{}" hx-target="#modal-slot" hx-swap="innerHTML">{}</button>',
            reverse("cartera-editar", args=[cliente.pk]),
            reverse("cartera-archivar", args=[cliente.pk]),
            "Archivar" if cliente.activo else "Reactivar",
        )
    ultima_visita = None
    try:
        from apps.checador.services import ultima_ubicacion_de
        ultima_visita = ultima_ubicacion_de(cliente=cliente)
    except Exception:  # noqa: BLE001 — la ubicación nunca tumba el perfil
        pass
    # LC 2026-08-04 (Oscar): botón «+ Nuevo proyecto» para ESTE cliente. Se gatea
    # con el permiso de crear proyectos, no con el de ver la cartera.
    from lib.permisos import puede_editar_proyecto
    return render(request, "cartera/detalle.html", {
        "cliente": cliente,
        "puede_editar": puede_editar,
        "puede_crear_proyecto": puede_editar_proyecto(request.user, None),
        "ultima_visita": ultima_visita,
        "contactos": list(cliente.contactos.all()),
        "proyectos_por_estado": proyectos_por_estado,
        # LC 2026-07-25: en la ficha se ve TODO lo ligado al cliente.
        "ligado": _ligado_del_cliente(cliente),
        "kpis_cliente": kpis_cliente,
        "action_bar_meta": action_bar_meta,
        "action_bar_acciones": action_bar_acciones,
        "breadcrumb_items": [
            {"url": reverse("cartera-lista"), "label": "Clientes"},
            {"label": cliente.razon_social},
        ],
        "back_url": reverse("cartera-lista"),
        "back_label": "Clientes",
    })


@login_required
@require_http_methods(["POST"])
def cliente_celda(request, pk):
    """Guardado por celda de la edición rápida (mismo patrón que Productos).
    Whitelist: nombre (razon_social), teléfono, estado. Responde 204 (sin swap).
    El teléfono se sincroniza también en el contacto principal (fuente de verdad),
    así el espejo legacy no lo revierte en el siguiente guardado del formulario."""
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Sin permiso para editar clientes.")
    cliente = get_object_or_404(Cliente, pk=pk)
    campo = (request.POST.get("campo") or "").strip()
    valor = (request.POST.get("valor") or "").strip()

    if campo == "razon_social":
        valor = valor.upper()[:200]
        if not valor:
            return HttpResponseBadRequest("El nombre no puede quedar vacío.")
        cliente.razon_social = valor
        cliente.save(update_fields=["razon_social", "actualizado_en"])
    elif campo == "razon_social_fiscal":
        cliente.razon_social_fiscal = valor.upper()[:200]
        cliente.save(update_fields=["razon_social_fiscal", "actualizado_en"])
        # LC 2026-07-26: la lista edita el campo legacy; la razón social
        # PRINCIPAL se sincroniza para que las dos vistas digan lo mismo.
        from apps.la_cartera.services import asegurar_razon_principal
        asegurar_razon_principal(cliente)
    elif campo == "telefono":
        valor = valor[:40]
        cliente.telefono = valor
        cliente.save(update_fields=["telefono", "actualizado_en"])
        cp = cliente.contacto_principal
        if cp is not None:
            cp.telefono = valor
            cp.save(update_fields=["telefono"])
    elif campo == "estado":
        if valor not in {c[0] for c in ESTADOS_CLIENTE}:
            return HttpResponseBadRequest("Estado no válido.")
        cliente.estado = valor
        cliente.save(update_fields=["estado", "actualizado_en"])
    else:
        return HttpResponseBadRequest("Campo no editable.")

    emitir(EventoPortavoz(
        tipo="cliente.actualizado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"cliente_id": cliente.pk, "campo": campo, "origen": "celda_inline"},
    ))
    return HttpResponse(status=204)


@login_required
@require_http_methods(["POST"])
def cliente_eliminar(request, pk):
    """Borrado PERMANENTE de un cliente ARCHIVADO (limpieza). Destructivo:
    solo con permiso `cartera.eliminar` (super_admin por default). Se exige que
    el cliente esté archivado y NO tenga proyectos ligados (FK PROTECT / historial)."""
    if not puede_eliminar_cartera(request.user):
        return HttpResponseForbidden("Sin permiso para eliminar clientes.")
    cliente = get_object_or_404(Cliente, pk=pk)
    if cliente.activo:
        messages.error(request, "Archiva el cliente antes de eliminarlo permanentemente.")
        return redirect("cartera-detalle", pk=cliente.pk)
    # LC 2026-07-25: el aviso dice EXACTAMENTE qué lo bloquea (antes era un
    # genérico "facturas u otros movimientos" que parecía falso, porque quien
    # bloqueaba eran cotizaciones que no se veían en ningún lado).
    bloqueos = _ligado_del_cliente(cliente)["bloqueos"]
    if bloqueos:
        detalle_txt = "; ".join(f"{b['tipo']} {b['etiqueta']}" for b in bloqueos[:6])
        extra = f" y {len(bloqueos) - 6} más" if len(bloqueos) > 6 else ""
        messages.error(
            request,
            f"No se puede eliminar: sigue ligado a {detalle_txt}{extra}. "
            f"Elimina o suelta esos registros (las cotizaciones anuladas se pueden "
            f"eliminar desde su página) o déjalo archivado.",
        )
        return redirect("cartera-detalle", pk=cliente.pk)
    from django.db.models import ProtectedError
    razon = cliente.razon_social
    cliente_id = cliente.pk
    try:
        cliente.delete()
    except ProtectedError:
        # Red de seguridad: algún FK PROTECT que no esté en `bloqueos`.
        messages.error(request, "No se puede eliminar: el cliente tiene movimientos ligados que lo protegen. Archívalo en su lugar.")
        return redirect("cartera-detalle", pk=cliente_id)
    emitir(EventoPortavoz(
        tipo="cliente.eliminado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"cliente_id": cliente_id, "razon_social": razon},
    ))
    messages.success(request, f"Cliente «{razon}» eliminado permanentemente.")
    return redirect("cartera-lista")


@login_required
def cliente_quick_create(request):
    """Alta mínima de cliente vía JSON (S-LC-Buzon). Usado inline desde el form
    de Ingreso. Sólo razón social es obligatoria."""
    if request.method != "POST" or not puede_editar_cartera(request.user):
        return HttpResponseForbidden("No autorizado.")
    from django.http import JsonResponse
    razon = (request.POST.get("razon_social") or "").strip().upper()
    if not razon:
        return JsonResponse({"ok": False, "error": "La razón social es obligatoria."})
    nombre_c = (request.POST.get("nombre_contacto") or "").strip()
    email_c = (request.POST.get("email_contacto") or "").strip()
    tel_c = (request.POST.get("telefono") or "").strip()
    cliente = Cliente.objects.create(
        razon_social=razon,
        rfc=(request.POST.get("rfc") or "").strip().upper(),
        nombre_contacto=nombre_c,
        email_contacto=email_c,
        telefono=tel_c,
        creado_por=request.user,
    )
    from apps.la_cartera.services import asegurar_contacto_principal
    asegurar_contacto_principal(cliente)
    emitir(EventoPortavoz(
        tipo="cliente.creado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"cliente_id": cliente.pk, "razon_social": cliente.razon_social, "origen": "quick_create_ingreso"},
    ))
    return JsonResponse({"ok": True, "id": cliente.pk, "razon_social": cliente.razon_social})


def _razones_del_post(request, instance=None):
    """Formset de razones sociales, sólo si su management form llegó.

    Hay rutas que capturan al cliente sin esta sección (el quick-create HTMX, y
    cualquier POST viejo que quedara en una pestaña abierta). Ahí devolvemos
    None: la sección se omite en lugar de invalidar todo el guardado.
    """
    prefijo = ClienteRazonSocialFormSet.get_default_prefix()
    if f"{prefijo}-TOTAL_FORMS" not in request.POST:
        return None
    return ClienteRazonSocialFormSet(request.POST, instance=instance)


@login_required
def nuevo(request):
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden crear clientes.")
    # Revisión buzón R2: form-in-modal si es HTMX (#modal-slot); POST HTMX → 204
    # + HX-Redirect al detalle. La página full queda de fallback.
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = ClienteForm(request.POST)
        # LC Fase 2: el quick-create (HTMX) es ultra-compacto — solo Nombre +
        # estado. Sin el formset de Contactos (se capturan luego en la ficha);
        # `asegurar_contacto_principal` deja un contacto principal si más tarde
        # se llenan los datos legacy.
        formset = None if es_htmx else ClienteContactoFormSet(request.POST)
        # LC 2026-07-26: razones sociales de facturación (varias, cada una con su
        # RFC). Igual que Contactos: fuera del quick-create HTMX.
        formset_razones = None if es_htmx else _razones_del_post(request)
        if (form.is_valid() and (formset is None or formset.is_valid())
                and (formset_razones is None or formset_razones.is_valid())):
            from apps.la_cartera.services import (
                asegurar_contacto_principal,
                espejar_contacto_principal,
                espejar_razon_principal,
            )
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            if formset is not None:
                formset.instance = cliente
                formset.save()
                espejar_contacto_principal(cliente)
            else:
                asegurar_contacto_principal(cliente)
            if formset_razones is not None:
                formset_razones.instance = cliente
                formset_razones.save()
                espejar_razon_principal(cliente)
            emitir(EventoPortavoz(
                tipo="cliente.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"cliente_id": cliente.pk, "razon_social": cliente.razon_social, "rfc": cliente.rfc},
            ))
            messages.success(request, f"Cliente «{cliente.razon_social}» creado.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": reverse("cartera-detalle", args=[cliente.pk])})
            return redirect("cartera-detalle", pk=cliente.pk)
        # inválido → cae al render (modal si es HTMX).
    else:
        form = ClienteForm()
        formset = ClienteContactoFormSet()
        formset_razones = ClienteRazonSocialFormSet()
    ctx = {"form": form, "formset": formset, "formset_razones": formset_razones, "modo": "nuevo", "breadcrumb_items": [{"url": "/cartera/", "label": "Clientes"}, {"label": "Nuevo cliente"}], "back_url": "/cartera/", "back_label": "Clientes"}
    tmpl = "cartera/_modal_nuevo_cliente.html" if es_htmx else "cartera/form.html"
    return render(request, tmpl, ctx)


@login_required
def editar(request, pk):
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden editar clientes.")
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        formset = ClienteContactoFormSet(request.POST, instance=cliente)
        formset_razones = _razones_del_post(request, instance=cliente)
        if (form.is_valid() and formset.is_valid()
                and (formset_razones is None or formset_razones.is_valid())):
            from apps.la_cartera.services import (
                espejar_contacto_principal,
                espejar_razon_principal,
            )
            form.save()
            formset.save()
            espejar_contacto_principal(cliente)
            if formset_razones is not None:
                formset_razones.save()
                espejar_razon_principal(cliente)
            emitir(EventoPortavoz(
                tipo="cliente.actualizado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"cliente_id": cliente.pk},
            ))
            messages.success(request, "Cliente actualizado.")
            return redirect("cartera-detalle", pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)
        formset = ClienteContactoFormSet(instance=cliente)
        formset_razones = ClienteRazonSocialFormSet(instance=cliente)
    return render(request, "cartera/form.html", {"form": form, "formset": formset, "formset_razones": formset_razones, "modo": "editar", "cliente": cliente, "breadcrumb_items": [{"url": "/cartera/", "label": "Clientes"}, {"url": f"/cartera/{cliente.pk}/", "label": cliente.razon_social}, {"label": "Editar"}], "back_url": f"/cartera/{cliente.pk}/", "back_label": cliente.razon_social})


@login_required
def archivar(request, pk):
    """Soft delete: activo=False. GET (HTMX) → modal de confirmación; POST → acción."""
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden archivar clientes.")
    cliente = get_object_or_404(Cliente, pk=pk)
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        cliente.activo = not cliente.activo
        cliente.save(update_fields=["activo", "actualizado_en"])
        messages.success(request, "Cliente " + ("archivado." if not cliente.activo else "reactivado."))
        destino = reverse("cartera-detalle", args=[cliente.pk])
        if es_htmx:
            return HttpResponse(status=204, headers={"HX-Redirect": destino})
        return redirect(destino)
    if es_htmx:
        return render(request, "cartera/_modal_archivar.html", {"cliente": cliente})
    return redirect("cartera-detalle", pk=pk)
