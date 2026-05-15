"""El Catálogo — CRUD de servicios + categorías. Admin (super_admin/dueno)
puede mutar; contador solo lee; disenador no entra."""

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from lib.permisos import es_admin
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import CategoriaForm, ServicioForm
from .models import CategoriaServicio, Servicio


def _puede_ver(user) -> bool:
    return getattr(user, "rol", None) in ("super_admin", "dueno", "contador")


def _gate_ver(request):
    if not request.user.is_authenticated:
        return redirect("/sign-in")
    if not _puede_ver(request.user):
        return HttpResponseForbidden("Sin acceso a El Catálogo.")
    return None


def _gate_editar(request):
    if not request.user.is_authenticated:
        return redirect("/sign-in")
    if not es_admin(request.user):
        return HttpResponseForbidden("Solo super_admin y dueño editan El Catálogo.")
    return None


def lista(request):
    if (r := _gate_ver(request)) is not None:
        return r
    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    incluir_archivados = request.GET.get("archivados") == "1" and es_admin(request.user)
    qs = Servicio.objects.select_related("categoria")
    if not incluir_archivados:
        qs = qs.filter(activo=True)
    if q:
        qs = qs.filter(nombre__icontains=q)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    return render(request, "catalogo/lista.html", {
        "servicios": qs,
        "categorias": CategoriaServicio.objects.filter(activa=True),
        "q": q,
        "categoria_filtro": categoria_id,
        "incluir_archivados": incluir_archivados,
        "puede_editar": es_admin(request.user),
    })


@require_http_methods(["GET", "POST"])
def nuevo(request):
    if (r := _gate_editar(request)) is not None:
        return r
    if request.method == "POST":
        form = ServicioForm(request.POST)
        if form.is_valid():
            srv = form.save(commit=False)
            srv.creado_por = request.user
            srv.save()
            emitir(EventoPortavoz(
                tipo="catalogo.servicio_creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk, "nombre": srv.nombre, "categoria": srv.categoria.nombre},
            ))
            messages.success(request, f"Servicio «{srv.nombre}» creado.")
            return redirect("catalogo-lista")
    else:
        form = ServicioForm()
    return render(request, "catalogo/form.html", {"form": form, "modo": "nuevo"})


@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    if (r := _gate_editar(request)) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    if request.method == "POST":
        form = ServicioForm(request.POST, instance=srv)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="catalogo.servicio_actualizado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk},
            ))
            messages.success(request, "Servicio actualizado.")
            return redirect("catalogo-lista")
    else:
        form = ServicioForm(instance=srv)
    return render(request, "catalogo/form.html", {"form": form, "modo": "editar", "servicio": srv})


@require_http_methods(["POST"])
def archivar(request, pk: int):
    if (r := _gate_editar(request)) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    srv.activo = not srv.activo
    srv.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, "Servicio " + ("archivado." if not srv.activo else "reactivado."))
    return redirect("catalogo-lista")


# ── Categorías ───────────────────────────────────────────────────────────────

def categorias_lista(request):
    if (r := _gate_ver(request)) is not None:
        return r
    cats = CategoriaServicio.objects.all()
    return render(request, "catalogo/categorias.html", {
        "categorias": cats,
        "puede_editar": es_admin(request.user),
    })


@require_http_methods(["GET", "POST"])
def categoria_nueva(request):
    if (r := _gate_editar(request)) is not None:
        return r
    if request.method == "POST":
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría creada.")
            return redirect("catalogo-categorias")
    else:
        form = CategoriaForm()
    return render(request, "catalogo/categoria_form.html", {"form": form, "modo": "nuevo"})


@require_http_methods(["GET", "POST"])
def categoria_editar(request, pk: int):
    if (r := _gate_editar(request)) is not None:
        return r
    cat = get_object_or_404(CategoriaServicio, pk=pk)
    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría actualizada.")
            return redirect("catalogo-categorias")
    else:
        form = CategoriaForm(instance=cat)
    return render(request, "catalogo/categoria_form.html", {"form": form, "modo": "editar", "categoria": cat})
