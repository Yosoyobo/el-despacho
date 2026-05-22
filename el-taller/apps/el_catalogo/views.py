"""El Catálogo — CRUD de servicios + categorías.

Pre-S2b.2: movido de La Gerencia a El Taller. Permisos granulares
toggleables individualmente via tabla `cuentas_permiso_usuario`:

  catalogo.ver_nombres         → Lista visible + módulo en sidebar
  catalogo.ver_precios         → Columna de precio en lista/detalle visible
  catalogo.crear               → Botón "Nuevo servicio"
  catalogo.editar              → Botón "Editar"
  catalogo.editar_precios      → Campo precio editable en form (subset de editar)
  catalogo.archivar            → Botón "Archivar/Reactivar"
  catalogo.gestionar_categorias → Submenú de categorías + CRUD
"""

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from lib.permisos import puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import CategoriaForm, ServicioForm, VariacionForm
from .models import CategoriaServicio, Servicio, Variacion


def _gate(request, accion: str):
    """Helper: 302 a /sign-in si no auth, 403 si no tiene el permiso, None si OK."""
    if not request.user.is_authenticated:
        return redirect("/sign-in")
    if not puede(request.user, "catalogo", accion):
        return HttpResponseForbidden(f"Sin permiso catalogo.{accion}.")
    return None


def lista(request):
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    user = request.user
    ve_precios = puede(user, "catalogo", "ver_precios")
    puede_crear = puede(user, "catalogo", "crear")
    puede_editar = puede(user, "catalogo", "editar")
    puede_archivar = puede(user, "catalogo", "archivar")
    puede_gestionar_cats = puede(user, "catalogo", "gestionar_categorias")

    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    incluir_archivados = request.GET.get("archivados") == "1" and puede_archivar
    qs = Servicio.objects.select_related("categoria")
    if not incluir_archivados:
        qs = qs.filter(activo=True)
    if q:
        qs = qs.filter(nombre__icontains=q)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    cabeceras = [{"label": "Nombre"}, {"label": "Categoría"}, {"label": "Unidad"}]
    if ve_precios:
        cabeceras.append({"label": "Precio base", "align": "right"})
    cabeceras.append({"label": "Estado"})
    if puede_editar or puede_archivar:
        cabeceras.append({"label": "", "align": "right"})
    return render(request, "catalogo/lista.html", {
        "servicios": qs,
        "categorias": CategoriaServicio.objects.filter(activa=True),
        "q": q,
        "categoria_filtro": categoria_id,
        "incluir_archivados": incluir_archivados,
        "ve_precios": ve_precios,
        "puede_crear": puede_crear,
        "puede_editar": puede_editar,
        "puede_archivar": puede_archivar,
        "puede_gestionar_cats": puede_gestionar_cats,
        "cabeceras_catalogo": cabeceras,
    })


@require_http_methods(["GET", "POST"])
def nuevo(request):
    if (r := _gate(request, "crear")) is not None:
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
    return render(request, "catalogo/form.html", {
        "form": form, "modo": "nuevo",
        "precio_readonly": not puede(request.user, "catalogo", "editar_precios"),
    })


@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    if (r := _gate(request, "editar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    puede_editar_precios = puede(request.user, "catalogo", "editar_precios")
    if request.method == "POST":
        form = ServicioForm(request.POST, instance=srv)
        if form.is_valid():
            obj = form.save(commit=False)
            # Si no tiene editar_precios, restauramos el precio original.
            if not puede_editar_precios:
                obj.precio_base = srv.precio_base
            obj.save()
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
    return render(request, "catalogo/form.html", {
        "form": form, "modo": "editar", "servicio": srv,
        "precio_readonly": not puede_editar_precios,
    })


@require_http_methods(["POST"])
def archivar(request, pk: int):
    if (r := _gate(request, "archivar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    srv.activo = not srv.activo
    srv.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, "Servicio " + ("archivado." if not srv.activo else "reactivado."))
    return redirect("catalogo-lista")


# ── Variaciones ──────────────────────────────────────────────────────────────

def variaciones_lista(request, pk: int):
    """Detalle del servicio + listado de variaciones."""
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    variaciones = srv.variaciones.all()
    return render(request, "catalogo/variaciones.html", {
        "servicio": srv,
        "variaciones": variaciones,
        "puede_editar": puede(request.user, "catalogo", "editar"),
        "puede_archivar": puede(request.user, "catalogo", "archivar"),
    })


@require_http_methods(["GET", "POST"])
def variacion_nueva(request, pk: int):
    if (r := _gate(request, "crear")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    if request.method == "POST":
        form = VariacionForm(request.POST)
        if form.is_valid():
            v = form.save(commit=False)
            v.servicio = srv
            v.save()
            emitir(EventoPortavoz(
                tipo="catalogo.variacion_creada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk, "variacion_id": v.pk, "nombre": v.nombre},
            ))
            messages.success(request, f"Variación «{v.nombre}» creada.")
            return redirect("catalogo-variaciones", pk=srv.pk)
    else:
        form = VariacionForm()
    return render(request, "catalogo/variacion_form.html", {
        "form": form, "servicio": srv, "modo": "nueva",
    })


@require_http_methods(["GET", "POST"])
def variacion_editar(request, pk: int, vpk: int):
    if (r := _gate(request, "editar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    v = get_object_or_404(Variacion, pk=vpk, servicio=srv)
    if request.method == "POST":
        form = VariacionForm(request.POST, instance=v)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="catalogo.variacion_actualizada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk, "variacion_id": v.pk},
            ))
            messages.success(request, "Variación actualizada.")
            return redirect("catalogo-variaciones", pk=srv.pk)
    else:
        form = VariacionForm(instance=v)
    return render(request, "catalogo/variacion_form.html", {
        "form": form, "servicio": srv, "variacion": v, "modo": "editar",
    })


@require_http_methods(["POST"])
def variacion_archivar(request, pk: int, vpk: int):
    if (r := _gate(request, "archivar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    v = get_object_or_404(Variacion, pk=vpk, servicio=srv)
    v.disponible = not v.disponible
    v.save(update_fields=["disponible", "actualizado_en"])
    messages.success(request, "Variación " + ("ocultada." if not v.disponible else "disponible."))
    return redirect("catalogo-variaciones", pk=srv.pk)


# ── Categorías ───────────────────────────────────────────────────────────────

def categorias_lista(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    cats = CategoriaServicio.objects.all()
    return render(request, "catalogo/categorias.html", {"categorias": cats})


@require_http_methods(["GET", "POST"])
def categoria_nueva(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
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
    if (r := _gate(request, "gestionar_categorias")) is not None:
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
