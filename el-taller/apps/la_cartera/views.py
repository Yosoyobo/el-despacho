from apps.la_cartera.forms import ClienteForm
from apps.la_cartera.models import Cliente
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import puede_editar_cartera, puede_ver_cartera
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _gate(request, ver=True):
    if ver and not puede_ver_cartera(request.user):
        return HttpResponseForbidden("Sin acceso a La Cartera.")
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
    # KPIs hero
    activos = Cliente.activos.count()
    archivados = Cliente.objects.filter(activo=False).count()
    con_proyectos_activos = Cliente.activos.filter(
        proyectos__estado__in=("en_diseno", "revision_cliente", "en_produccion")
    ).distinct().count()
    return render(request, "cartera/lista.html", {
        "clientes": qs,
        "q": q,
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
    return render(request, "cartera/detalle.html", {
        "cliente": cliente,
        "puede_editar": puede_editar_cartera(request.user),
        "proyectos": cliente.proyectos.all(),
    })


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
    return render(request, "cartera/form.html", {"form": form, "modo": "nuevo", "breadcrumb_items": [{"url": "/cartera/", "label": "La Cartera"}, {"label": "Nuevo cliente"}]})


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
    return render(request, "cartera/form.html", {"form": form, "modo": "editar", "cliente": cliente, "breadcrumb_items": [{"url": "/cartera/", "label": "La Cartera"}, {"url": f"/cartera/{cliente.pk}/", "label": cliente.razon_social}, {"label": "Editar"}]})


@login_required
def archivar(request, pk):
    """Soft delete: activo=False. POST-only."""
    if not puede_editar_cartera(request.user):
        return HttpResponseForbidden("Solo admins pueden archivar clientes.")
    if request.method != "POST":
        return redirect("cartera-detalle", pk=pk)
    cliente = get_object_or_404(Cliente, pk=pk)
    cliente.activo = not cliente.activo
    cliente.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, "Cliente " + ("archivado." if not cliente.activo else "reactivado."))
    return redirect("cartera-detalle", pk=cliente.pk)
