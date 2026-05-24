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

from .forms import CategoriaForm, ProveedorForm, ServicioForm, UnidadForm, VariacionForm
from .models import CategoriaServicio, Proveedor, Servicio, Unidad, Variacion


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
    qs = Servicio.objects.select_related("categoria").prefetch_related("proveedores")
    if not incluir_archivados:
        qs = qs.filter(activo=True)
    if q:
        qs = qs.filter(nombre__icontains=q)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    cabeceras = [{"label": "Nombre"}, {"label": "Categoría"}, {"label": "Unidad"}]
    if ve_precios:
        cabeceras.append({"label": "Costo", "align": "right"})
        cabeceras.append({"label": "Precio", "align": "right"})
        cabeceras.append({"label": "Margen", "align": "right"})
    cabeceras.append({"label": "Proveedores"})
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


# ── Unidades (S-LC-Feedback-V2) ─────────────────────────────────────────────

def unidades_lista(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    incluir_archivadas = request.GET.get("archivadas") == "1"
    qs = Unidad.objects.all() if incluir_archivadas else Unidad.objects.filter(activa=True)
    return render(request, "catalogo/unidades.html", {
        "unidades": qs,
        "incluir_archivadas": incluir_archivadas,
    })


@require_http_methods(["GET", "POST"])
def unidad_nueva(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    if request.method == "POST":
        form = UnidadForm(request.POST)
        if form.is_valid():
            u = form.save()
            emitir(EventoPortavoz(
                tipo="catalogo.unidad_creada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"unidad_id": u.pk, "nombre": u.nombre},
            ))
            messages.success(request, f"Unidad '{u.nombre}' creada.")
            return redirect("catalogo-unidades")
    else:
        form = UnidadForm()
    return render(request, "catalogo/unidad_form.html", {"form": form, "modo": "nuevo"})


@require_http_methods(["GET", "POST"])
def unidad_editar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    u = get_object_or_404(Unidad, pk=pk)
    if request.method == "POST":
        form = UnidadForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="catalogo.unidad_actualizada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"unidad_id": u.pk, "nombre": u.nombre},
            ))
            messages.success(request, "Unidad actualizada.")
            return redirect("catalogo-unidades")
    else:
        form = UnidadForm(instance=u)
    return render(request, "catalogo/unidad_form.html", {"form": form, "modo": "editar", "unidad": u})


@require_http_methods(["POST"])
def unidad_archivar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    u = get_object_or_404(Unidad, pk=pk)
    u.activa = not u.activa
    u.save(update_fields=["activa"])
    messages.success(request, f"Unidad '{u.nombre}' " + ("desactivada." if not u.activa else "activada."))
    return redirect("catalogo-unidades")


# ── Quick-create de Servicio (S-LC-Feedback-V2) ─────────────────────────────

@require_http_methods(["POST"])
def servicio_quick_create(request):
    """POST /catalogo/quick-create/ — crea Servicio inline desde el form de Proyecto.

    Espera POST con: nombre, categoria_id, precio_base, unidad (default 'pieza').
    Retorna JSON con id + nombre + categoria_nombre + precio para que el JS
    del form de Proyecto agregue la opción al select y la seleccione.
    """
    if (r := _gate(request, "crear")) is not None:
        return r
    from django.http import JsonResponse
    nombre = (request.POST.get("nombre") or "").strip()
    categoria_id = request.POST.get("categoria_id")
    precio_raw = (request.POST.get("precio_base") or "").strip()
    costo_raw = (request.POST.get("costo") or "0").strip() or "0"
    unidad = (request.POST.get("unidad") or "pieza").strip() or "pieza"
    if not nombre or not categoria_id or not precio_raw:
        return JsonResponse({"ok": False, "error": "Faltan campos requeridos."}, status=400)
    try:
        precio = float(precio_raw)
        costo = float(costo_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Precio o costo inválido."}, status=400)
    try:
        categoria = CategoriaServicio.objects.get(pk=categoria_id, activa=True)
    except CategoriaServicio.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Categoría no encontrada."}, status=400)
    s = Servicio.objects.create(
        nombre=nombre,
        categoria=categoria,
        precio_base=precio,
        costo=costo,
        unidad=unidad,
        creado_por=request.user,
    )
    emitir(EventoPortavoz(
        tipo="catalogo.servicio_quick_creado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"servicio_id": s.pk, "nombre": s.nombre, "categoria": categoria.nombre},
    ))
    return JsonResponse({
        "ok": True,
        "id": s.pk,
        "nombre": s.nombre,
        "categoria_nombre": categoria.nombre,
        "precio": str(s.precio_base),
        "costo": str(s.costo),
        "margen": s.margen_porcentaje,
        "label": f"{s.nombre} ({categoria.nombre})",
    })


# ── Proveedores (S-LC-Feedback-V3) ──────────────────────────────────────────

def proveedores_lista(request):
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    incluir_archivados = request.GET.get("archivados") == "1"
    qs = Proveedor.objects.all() if incluir_archivados else Proveedor.objects.filter(activo=True)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(razon_social__icontains=q)
    return render(request, "catalogo/proveedores_lista.html", {
        "proveedores": qs.order_by("razon_social"),
        "q": q,
        "incluir_archivados": incluir_archivados,
    })


@require_http_methods(["POST"])
def proveedor_quick_create(request):
    """POST /catalogo/proveedores/quick-create/ — crea Proveedor inline desde el form de Servicio.

    Espera POST con: razon_social (requerido), nombre_contacto, email_contacto, telefono.
    Retorna JSON con id + razon_social para que el JS agregue un checkbox marcado.
    Requiere permiso `crear` del módulo catálogo (el mismo que crea servicios).
    """
    if (r := _gate(request, "crear")) is not None:
        return r
    from django.http import JsonResponse
    razon = (request.POST.get("razon_social") or "").strip()
    if not razon:
        return JsonResponse({"ok": False, "error": "La razón social es obligatoria."}, status=400)
    prov = Proveedor.objects.create(
        razon_social=razon,
        nombre_contacto=(request.POST.get("nombre_contacto") or "").strip(),
        email_contacto=(request.POST.get("email_contacto") or "").strip(),
        telefono=(request.POST.get("telefono") or "").strip(),
        creado_por=request.user,
    )
    emitir(EventoPortavoz(
        tipo="proveedor.quick_creado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"proveedor_id": prov.pk, "razon_social": prov.razon_social},
    ))
    return JsonResponse({"ok": True, "id": prov.pk, "razon_social": prov.razon_social})


@require_http_methods(["GET", "POST"])
def proveedor_nuevo(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            prov = form.save(commit=False)
            prov.creado_por = request.user
            prov.save()
            emitir(EventoPortavoz(
                tipo="proveedor.creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proveedor_id": prov.pk, "razon_social": prov.razon_social},
            ))
            messages.success(request, f"Proveedor '{prov.razon_social}' creado.")
            return redirect("catalogo-proveedores")
    else:
        form = ProveedorForm()
    return render(request, "catalogo/proveedor_form.html", {"form": form, "modo": "nuevo"})


def proveedor_detalle(request, pk: int):
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    return render(request, "catalogo/proveedor_detalle.html", {
        "proveedor": prov,
        "servicios": prov.servicios.filter(activo=True),
    })


@require_http_methods(["GET", "POST"])
def proveedor_editar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=prov)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proveedor.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proveedor_id": prov.pk},
            ))
            messages.success(request, "Proveedor actualizado.")
            return redirect("catalogo-proveedor-detalle", pk=prov.pk)
    else:
        form = ProveedorForm(instance=prov)
    return render(request, "catalogo/proveedor_form.html", {"form": form, "modo": "editar", "proveedor": prov})


@require_http_methods(["POST"])
def proveedor_archivar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    prov.activo = not prov.activo
    prov.save(update_fields=["activo"])
    emitir(EventoPortavoz(
        tipo="proveedor.archivado" if not prov.activo else "proveedor.reactivado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"proveedor_id": prov.pk},
    ))
    messages.success(request, f"Proveedor '{prov.razon_social}' " + ("desactivado." if not prov.activo else "reactivado."))
    return redirect("catalogo-proveedores")
