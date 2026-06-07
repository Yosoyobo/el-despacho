from apps.la_cartera.forms import ClienteForm
from apps.la_cartera.models import Cliente
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html

from lib.permisos import puede_editar_cartera, puede_ver_cartera
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _gate(request, ver=True):
    if ver and not puede_ver_cartera(request.user):
        return HttpResponseForbidden("Sin acceso a Clientes.")
    return None


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    q = (request.GET.get("q") or "").strip()
    incluir_archivados = request.GET.get("archivados") == "1" and puede_editar_cartera(request.user)
    qs = Cliente.objects.all() if incluir_archivados else Cliente.activos.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(razon_social__icontains=q) | Q(rfc__icontains=q) | Q(email_contacto__icontains=q))
    orden_permitido = {"razon_social", "rfc", "estado", "creado_en"}
    orden = (request.GET.get("orden") or "razon_social").strip()
    orden_clean = orden.lstrip("-")
    if orden_clean not in orden_permitido:
        orden = "razon_social"
    qs = qs.order_by(orden, "pk")
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    # KPIs hero
    activos = Cliente.activos.count()
    archivados = Cliente.objects.filter(activo=False).count()
    con_proyectos_activos = Cliente.activos.filter(
        proyectos__estado__in=("en_diseno", "revision_cliente", "en_produccion")
    ).distinct().count()
    qs_filtros = []
    if q:
        qs_filtros.append(f"q={q}")
    if incluir_archivados:
        qs_filtros.append("archivados=1")
    querystring_base = "&".join(qs_filtros)
    return render(request, "cartera/lista.html", {
        "clientes": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "querystring_paginacion": "&".join(qs_filtros + ([f"orden={orden}"] if orden != "razon_social" else [])),
        "cabeceras_cartera": [
            {"label": "Razón social", "sort_key": "razon_social"},
            {"label": "RFC", "sort_key": "rfc"},
            {"label": "Contacto"},
            {"label": "Estado", "sort_key": "estado"},
            {"label": "Acciones", "align": "right"},
        ],
        "incluir_archivados": incluir_archivados,
        "puede_editar": puede_editar_cartera(request.user),
        "kpis": {
            "activos": activos,
            "archivados": archivados,
            "con_proyectos": con_proyectos_activos,
            "sin_proyectos": activos - con_proyectos_activos,
        },
    })


@login_required
def detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    cliente = get_object_or_404(Cliente, pk=pk)
    puede_editar = puede_editar_cartera(request.user)
    info_identificacion = [
        {"label": "RFC", "value": cliente.rfc or "—", "mono": bool(cliente.rfc)},
        {"label": "Creado", "value": cliente.creado_en.strftime("%d %b %Y")},
    ]
    if cliente.creado_por:
        info_identificacion.append({"label": "Por", "value": cliente.creado_por.nombre_completo})
    info_contacto = [
        {"label": "Nombre", "value": cliente.nombre_contacto or "—"},
        {"label": "Email", "value": cliente.email_contacto or "—"},
        {"label": "Teléfono", "value": cliente.telefono or "—"},
    ]
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
    return render(request, "cartera/detalle.html", {
        "cliente": cliente,
        "puede_editar": puede_editar,
        "proyectos": cliente.proyectos.all(),
        "info_identificacion": info_identificacion,
        "info_contacto": info_contacto,
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
def cliente_quick_create(request):
    """Alta mínima de cliente vía JSON (S-LC-Buzon). Usado inline desde el form
    de Ingreso. Sólo razón social es obligatoria."""
    if request.method != "POST" or not puede_editar_cartera(request.user):
        return HttpResponseForbidden("No autorizado.")
    from django.http import JsonResponse
    razon = (request.POST.get("razon_social") or "").strip()
    if not razon:
        return JsonResponse({"ok": False, "error": "La razón social es obligatoria."})
    cliente = Cliente.objects.create(
        razon_social=razon,
        rfc=(request.POST.get("rfc") or "").strip().upper(),
        nombre_contacto=(request.POST.get("nombre_contacto") or "").strip(),
        email_contacto=(request.POST.get("email_contacto") or "").strip(),
        telefono=(request.POST.get("telefono") or "").strip(),
        creado_por=request.user,
    )
    emitir(EventoPortavoz(
        tipo="cliente.creado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"cliente_id": cliente.pk, "razon_social": cliente.razon_social, "origen": "quick_create_ingreso"},
    ))
    return JsonResponse({"ok": True, "id": cliente.pk, "razon_social": cliente.razon_social})


@login_required
def nuevo(request):
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden crear clientes.")
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            emitir(EventoPortavoz(
                tipo="cliente.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"cliente_id": cliente.pk, "razon_social": cliente.razon_social, "rfc": cliente.rfc},
            ))
            messages.success(request, f"Cliente «{cliente.razon_social}» creado.")
            return redirect("cartera-detalle", pk=cliente.pk)
    else:
        form = ClienteForm()
    return render(request, "cartera/form.html", {"form": form, "modo": "nuevo", "breadcrumb_items": [{"url": "/cartera/", "label": "Clientes"}, {"label": "Nuevo cliente"}], "back_url": "/cartera/", "back_label": "Clientes"})


@login_required
def editar(request, pk):
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden editar clientes.")
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
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
    return render(request, "cartera/form.html", {"form": form, "modo": "editar", "cliente": cliente, "breadcrumb_items": [{"url": "/cartera/", "label": "Clientes"}, {"url": f"/cartera/{cliente.pk}/", "label": cliente.razon_social}, {"label": "Editar"}], "back_url": f"/cartera/{cliente.pk}/", "back_label": cliente.razon_social})


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
