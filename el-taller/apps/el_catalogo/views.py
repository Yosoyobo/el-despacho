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
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from lib.permisos import puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import (
    CategoriaForm,
    CategoriaProveedorForm,
    ProveedorForm,
    ServicioForm,
    SubcategoriaProveedorForm,
    UnidadForm,
    VariacionForm,
)
from .models import (
    CategoriaProveedor,
    CategoriaServicio,
    Proveedor,
    Servicio,
    SubcategoriaProveedor,
    Unidad,
    Variacion,
)


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
    puede_eliminar = puede(user, "catalogo", "eliminar")
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
    # LC revisión buzón R2: modo edición inline (celdas editables) opt-in.
    editar_inline = request.GET.get("editar") == "1" and puede_editar
    cabeceras = [{"label": "Nombre"}, {"label": "Categoría"}, {"label": "Unidad"}]
    if ve_precios:
        cabeceras.append({"label": "Costo", "align": "right"})
        cabeceras.append({"label": "Precio", "align": "right"})
        cabeceras.append({"label": "Margen", "align": "right"})
    cabeceras.append({"label": "Proveedores"})
    cabeceras.append({"label": "Estado"})
    if editar_inline or puede_editar or puede_archivar or puede_eliminar:
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
        "puede_eliminar": puede_eliminar,
        "puede_gestionar_cats": puede_gestionar_cats,
        "cabeceras_catalogo": cabeceras,
        "editar_inline": editar_inline,
        "filas_template": "catalogo/_filas_editable.html" if editar_inline else "catalogo/_filas.html",
    })


@require_http_methods(["POST"])
def servicio_celda(request, pk: int):
    """Edición inline de UNA celda del producto (revisión buzón R2 — «tablas con
    celdas editables», por ahora solo en Productos). Whitelist de campos; guarda
    y responde 204 (el margen se recalcula en el cliente). Gated catalogo.editar.
    """
    if (r := _gate(request, "editar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    campo = (request.POST.get("campo") or "").strip()
    valor = request.POST.get("valor", "")
    if campo in {"costo", "precio_base"} and not puede(request.user, "catalogo", "ver_precios"):
        return HttpResponseForbidden("Sin permiso para editar precios.")
    if campo == "nombre":
        v = (valor or "").strip()
        if not v:
            return HttpResponseBadRequest("El nombre no puede quedar vacío.")
        srv.nombre = v[:150]
    elif campo == "unidad":
        srv.unidad = (valor or "").strip()[:30] or "pieza"
    elif campo in {"costo", "precio_base"}:
        from decimal import Decimal, InvalidOperation
        try:
            v = Decimal(str(valor).replace(",", "").strip() or "0")
        except InvalidOperation:
            return HttpResponseBadRequest("Número inválido.")
        if v < 0:
            return HttpResponseBadRequest("No puede ser negativo.")
        setattr(srv, campo, v)
    elif campo == "categoria":
        cat = CategoriaServicio.objects.filter(pk=valor if valor.isdigit() else 0).first()
        if not cat:
            return HttpResponseBadRequest("Categoría inválida.")
        srv.categoria = cat
    elif campo == "activo":
        srv.activo = str(valor) in {"1", "true", "on", "True", "si"}
    else:
        return HttpResponseBadRequest("Campo no editable.")
    srv.save(update_fields=[campo, "actualizado_en"])
    emitir(EventoPortavoz(
        tipo="catalogo.servicio_actualizado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"servicio_id": srv.pk, "campo": campo, "origen": "celda_inline"},
    ))
    return HttpResponse(status=204)


@require_http_methods(["GET", "POST"])
def servicio_eliminar(request, pk: int):
    """Borrado PERMANENTE de un producto (≠ archivar). S-LC-Feedback-V13.

    Bloqueado si el producto se usa en algún proyecto (ProyectoProducto tiene
    FK PROTECT): en ese caso se sugiere archivar. CotizacionItem/FacturaItem
    son SET_NULL (la línea conserva su descripción) y las variaciones caen en
    cascada. GET HTMX → modal de confirmación; POST → borra o reinyecta error.
    """
    if (r := _gate(request, "eliminar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    es_htmx = request.headers.get("HX-Request") == "true"
    usos_proyectos = srv.en_proyectos.count()
    ctx = {"servicio": srv, "usos_proyectos": usos_proyectos}
    if request.method == "POST":
        if usos_proyectos:
            msg = (f"No se puede eliminar «{srv.nombre}»: está usado en "
                   f"{usos_proyectos} producto(s) de proyecto. Archívalo en su lugar.")
            if es_htmx:
                return render(request, "catalogo/_modal_eliminar_servicio.html",
                              {**ctx, "error": msg})
            messages.error(request, msg)
            return redirect("catalogo-lista")
        nombre = srv.nombre
        emitir(EventoPortavoz(
            tipo="catalogo.servicio_eliminado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"servicio_id": srv.pk, "nombre": nombre},
        ))
        srv.delete()
        messages.success(request, f"Producto «{nombre}» eliminado permanentemente.")
        if es_htmx:
            return HttpResponse(status=204, headers={"HX-Redirect": reverse("catalogo-lista")})
        return redirect("catalogo-lista")
    if es_htmx:
        return render(request, "catalogo/_modal_eliminar_servicio.html", ctx)
    return redirect("catalogo-lista")


@require_http_methods(["GET", "POST"])
def nuevo(request):
    if (r := _gate(request, "crear")) is not None:
        return r
    # Revisión buzón R2: form-in-modal si es HTMX (#modal-slot); POST HTMX → 204
    # + HX-Redirect. La imagen sigue disponible solo al editar (Drive necesita
    # el producto guardado). La página full queda de fallback.
    es_htmx = request.headers.get("HX-Request") == "true"
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
            messages.success(request, f"Producto «{srv.nombre}» creado.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": reverse("catalogo-lista")})
            return redirect("catalogo-lista")
        # inválido → cae al render (modal si es HTMX).
    else:
        form = ServicioForm()
    ctx = {
        "form": form, "modo": "nuevo",
        "precio_readonly": not puede(request.user, "catalogo", "editar_precios"),
        **_navegacion_producto(request),
    }
    tmpl = "catalogo/_modal_nuevo_producto.html" if es_htmx else "catalogo/form.html"
    return render(request, tmpl, ctx)


def _navegacion_producto(request) -> dict:
    """Breadcrumb + back_url del form de producto según `?desde=` (Fase 3 §1.2).

    Cuando se llega DESDE un proveedor (`?desde=proveedor:<pk>`) la miga preserva
    el tramo `Productos › Proveedores › [Proveedor] › [Producto]` en vez de
    colapsar a `Productos › [Producto]`. Sin `desde`, la miga es la normal.
    """
    trail = [{"label": "Productos", "url": reverse("catalogo-lista")}]
    back_url = ""
    desde = (request.GET.get("desde") or "").strip()
    if desde.startswith("proveedor:"):
        pid = desde.split(":", 1)[1]
        if pid.isdigit():
            prov = Proveedor.objects.filter(pk=int(pid)).first()
            if prov is not None:
                url_prov = reverse("catalogo-proveedor-detalle", args=[prov.pk])
                trail += [
                    {"label": "Proveedores", "url": reverse("catalogo-proveedores")},
                    {"label": prov.razon_social, "url": url_prov},
                ]
                back_url = url_prov
    trail.append({"label": "Producto"})
    return {"breadcrumb_trail": trail, "back_url_producto": back_url}


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
            messages.success(request, "Producto actualizado.")
            # Fase 3 §1.2: si venía de un proveedor, regresa a su ficha.
            destino = _navegacion_producto(request).get("back_url_producto")
            return redirect(destino or reverse("catalogo-lista"))
    else:
        form = ServicioForm(instance=srv)
    return render(request, "catalogo/form.html", {
        "form": form, "modo": "editar", "servicio": srv,
        "precio_readonly": not puede_editar_precios,
        **_navegacion_producto(request),
    })


@require_http_methods(["POST"])
def archivar(request, pk: int):
    if (r := _gate(request, "archivar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    srv.activo = not srv.activo
    srv.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, "Producto " + ("archivado." if not srv.activo else "reactivado."))
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
    # Si llegó aquí, _gate confirmó que puede gestionar categorías.
    return render(request, "catalogo/categorias.html", {"categorias": cats, "puede_editar": True})


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


@require_http_methods(["POST"])
def categoria_borrar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    cat = get_object_or_404(CategoriaServicio, pk=pk)
    if cat.servicios.exists():
        messages.error(
            request,
            f"No se puede eliminar «{cat.nombre}»: tiene productos asociados. "
            "Desactívala o reasigna sus productos primero.",
        )
        return redirect("catalogo-categorias")
    nombre = cat.nombre
    cat.delete()
    messages.success(request, f"Categoría «{nombre}» eliminada.")
    return redirect("catalogo-categorias")


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

# Estados de proyecto que se consideran "cerrados" para el conteo de proyectos
# activos de un proveedor (entregado/cancelado son terminal=True). El resto
# (por cotizar, en proceso, en pausa, esperando respuesta) cuenta como activo.
_ESTADOS_PROYECTO_CERRADOS = {"entregado", "cancelado"}


def proveedores_lista(request):
    """Render LC 2026-06-30 — tarjetas de proveedor + filtro de dos niveles.

    Nivel 1 = Categorías (CategoriaServicio); nivel 2 = Servicios/productos
    (Servicio, cada uno con su categoría). Un proveedor surte ≥1 servicios
    (M2M `Servicio.proveedores`), de los que derivan sus categorías. Picar una
    categoría acota los chips de servicio Y los proveedores; picar un servicio
    acota los proveedores. La búsqueda y los resultados salen en el mismo
    formato de tarjetas.
    """
    from apps.los_proyectos.models import Proyecto
    from django.db.models import Q

    if (r := _gate(request, "ver_nombres")) is not None:
        return r

    incluir_archivados = request.GET.get("archivados") == "1"
    q = (request.GET.get("q") or "").strip()
    categoria_id = (request.GET.get("categoria") or "").strip()
    subcategoria_id = (request.GET.get("subcategoria") or "").strip()

    # ── Chips de filtro: taxonomía de PROVEEDOR (6 core → 19 subcategorías) ──
    # LC #164 (re-reporte): el 2º nivel muestra SUBCATEGORÍAS de proveedor, NO
    # productos del catálogo. Nivel 1 = CategoriaProveedor; nivel 2 =
    # SubcategoriaProveedor (lo mismo que ya pintan las tarjetas).
    categorias = list(
        CategoriaProveedor.objects.filter(activa=True).order_by("orden", "nombre")
    )
    subcats_qs = (
        SubcategoriaProveedor.objects.filter(activa=True)
        .select_related("categoria")
        .order_by("categoria__orden", "orden", "nombre")
    )
    # El segundo filtro se acota a la categoría elegida en el primero.
    if categoria_id.isdigit():
        subcats_qs = subcats_qs.filter(categoria_id=categoria_id)
    subcategorias_chips = list(subcats_qs)

    # ── Proveedores filtrados por la taxonomía ───────────────────────────
    qs = Proveedor.objects.all() if incluir_archivados else Proveedor.objects.filter(activo=True)
    if subcategoria_id.isdigit():
        qs = qs.filter(subcategorias__id=subcategoria_id)
    elif categoria_id.isdigit():
        qs = qs.filter(subcategorias__categoria_id=categoria_id)
    if q:
        qs = qs.filter(
            Q(razon_social__icontains=q)
            | Q(nombre_contacto__icontains=q)
            | Q(email_contacto__icontains=q)
            | Q(telefono__icontains=q)
            | Q(subcategorias__nombre__icontains=q)
            | Q(subcategorias__categoria__nombre__icontains=q)
            | Q(servicios__nombre__icontains=q)
            | Q(productos_proyecto__proyecto__codigo__icontains=q)
            | Q(productos_proyecto__proyecto__nombre__icontains=q)
        )
    qs = qs.distinct().order_by("razon_social").prefetch_related(
        "servicios__categoria", "subcategorias__categoria",
    )

    # ── Arma una tarjeta por proveedor (subcategorías + stats) ──
    # Las subcategorías (con su color heredado) se leen en el template desde
    # `t.obj.subcategorias.all` (ya prefetcheadas). Aquí sólo van los stats.
    tarjetas = []
    for prov in qs:
        productos = sum(1 for s in prov.servicios.all() if s.activo)
        # Proyectos ligados vía ProyectoProducto.proveedor (proveedor principal).
        estados = list(
            Proyecto.objects.filter(productos__proveedor=prov)
            .distinct()
            .values_list("estado", flat=True)
        )
        ubic = next((ln.strip() for ln in (prov.direccion or "").splitlines() if ln.strip()), "")
        tarjetas.append({
            "obj": prov,
            "productos": productos,
            "proyectos_totales": len(estados),
            "proyectos_activos": sum(1 for e in estados if e not in _ESTADOS_PROYECTO_CERRADOS),
            "ubicacion": ubic[:40],
        })

    # Params a preservar en los links de los chips (búsqueda + desactivados).
    from urllib.parse import urlencode
    preserva = []
    if q:
        preserva.append(("q", q))
    if incluir_archivados:
        preserva.append(("archivados", "1"))
    qs_preserva = urlencode(preserva)

    return render(request, "catalogo/proveedores_lista.html", {
        "tarjetas": tarjetas,
        "q": q,
        "incluir_archivados": incluir_archivados,
        "categorias": categorias,
        "subcategorias_chips": subcategorias_chips,
        "categoria_id": categoria_id if categoria_id.isdigit() else "",
        "subcategoria_id": subcategoria_id if subcategoria_id.isdigit() else "",
        "qs_preserva": qs_preserva,
        "puede_crear_prov": puede(request.user, "catalogo", "gestionar_categorias"),
        "puede_gestionar_categorias_prov": puede(request.user, "catalogo", "gestionar_categorias"),
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


@require_http_methods(["POST"])
def sugerir_proveedores(request):
    """POST /catalogo/sugerir-proveedores/ — El Chalán propone proveedores para
    el producto, según qué surte cada quien hoy (historial). Devuelve JSON con
    los ids a marcar. Gated por `crear` (mismo permiso que crea productos)."""
    if (r := _gate(request, "crear")) is not None:
        return r
    from django.http import JsonResponse

    from .services_sugerencia import sugerir_proveedores as _sugerir
    res = _sugerir(
        nombre=request.POST.get("nombre") or "",
        descripcion=request.POST.get("descripcion") or "",
        usuario=request.user,
    )
    return JsonResponse(res)


@require_http_methods(["GET", "POST"])
def proveedor_nuevo(request):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    # Revisión buzón R2: si es HTMX se sirve como form-in-modal (#modal-slot);
    # POST HTMX → 204 + HX-Redirect. La página full queda de fallback.
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            prov = form.save(commit=False)
            prov.creado_por = request.user
            prov.save()
            form.save_m2m()  # persiste subcategorías (LC 2026-07)
            emitir(EventoPortavoz(
                tipo="proveedor.creado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proveedor_id": prov.pk, "razon_social": prov.razon_social},
            ))
            messages.success(request, f"Proveedor '{prov.razon_social}' creado.")
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": reverse("catalogo-proveedores")})
            return redirect("catalogo-proveedores")
        # inválido → cae al render (modal si es HTMX).
    else:
        form = ProveedorForm()
    ctx = {
        "form": form, "modo": "nuevo",
        "categorias_prov": _categorias_prov(),
        "subcats_sel": {int(x) for x in request.POST.getlist("subcategorias")},
    }
    tmpl = "catalogo/_modal_nuevo_proveedor.html" if es_htmx else "catalogo/proveedor_form.html"
    return render(request, tmpl, ctx)


def _categorias_prov():
    """Categorías core de proveedor (con sus subcategorías) para los checkboxes."""
    from .models import CategoriaProveedor
    return CategoriaProveedor.objects.filter(activa=True).prefetch_related("subcategorias")


@require_http_methods(["GET", "POST"])
def proveedor_detalle(request, pk: int):
    """Detalle del proveedor con campos editables EN LÍNEA (render LC 2026-06-30,
    igual que la página de proyecto: sin botón «Editar», autoguardado HTMX).

    GET → ficha con el form inline. POST (HTMX) → valida + guarda + devuelve el
    indicador por OOB. El campo `activo` se excluye del form inline (lo maneja
    el botón Desactivar) para que el autoguardado no apague al proveedor.
    """
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    puede_editar = puede(request.user, "catalogo", "gestionar_categorias")
    es_htmx = request.headers.get("HX-Request") == "true"

    if request.method == "POST":
        if not puede_editar:
            return HttpResponseForbidden("Sin permiso para editar proveedores.")
        form = ProveedorForm(request.POST, instance=prov, inline=True)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="proveedor.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"proveedor_id": prov.pk, "campo": "detalle_inline"},
            ))
            if es_htmx:
                return render(request, "catalogo/_proveedor_guardado_oob.html",
                              {"proveedor": prov, "ok": True})
            messages.success(request, "Proveedor guardado.")
            return redirect("catalogo-proveedor-detalle", pk=prov.pk)
        if es_htmx:
            primer = next(
                (f"{form.fields[c].label or c}: {e[0]}" for c, e in form.errors.items() if e),
                "Revisa los campos.",
            )
            return render(request, "catalogo/_proveedor_guardado_oob.html",
                          {"proveedor": prov, "ok": False, "error_detalle": primer})
    else:
        form = ProveedorForm(instance=prov, inline=True)

    ultima_visita = None
    try:
        from apps.checador.services import ultima_ubicacion_de
        ultima_visita = ultima_ubicacion_de(proveedor=prov)
    except Exception:  # noqa: BLE001
        pass
    # LC 2026-07 (Wave 4): proyectos vigentes donde el proveedor está involucrado
    # (asignado formalmente o porque surte un producto del proyecto).
    from apps.los_proyectos.models import Proyecto as _Proyecto
    from django.db.models import Q as _Q
    _mgr = getattr(_Proyecto, "activos", _Proyecto.objects)
    proyectos_involucrados = (
        _mgr.filter(_Q(proveedores_asignados__proveedor=prov) | _Q(productos__proveedor=prov))
        .exclude(estado__in=["cancelado", "cerrado"])
        .select_related("cliente")
        .distinct().order_by("-creado_en")[:50]
    )

    return render(request, "catalogo/proveedor_detalle.html", {
        "proveedor": prov,
        "form": form,
        "puede_editar": puede_editar,
        "servicios": prov.servicios.filter(activo=True).select_related("categoria"),
        "proyectos_involucrados": proyectos_involucrados,
        "ultima_visita": ultima_visita,
        "categorias_prov": _categorias_prov(),
        "subcats_sel": set(prov.subcategorias.values_list("pk", flat=True)),
        "puede_gestionar_servicios": puede(request.user, "catalogo", "editar"),
        "puede_eliminar": puede(request.user, "catalogo", "eliminar"),
    })


@require_http_methods(["GET", "POST"])
def proveedor_servicios(request, pk: int):
    """Editor de la lista de servicios que surte un proveedor.

    Inverso del checkbox `proveedores` en el form de Servicio: aquí marcas
    productos desde la perspectiva del proveedor. Misma M2M, gated por el
    permiso `editar` del catálogo (mismo que tocar la lista del lado servicio).
    """
    if (r := _gate(request, "editar")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        ids = request.POST.getlist("servicios")
        try:
            ids_int = [int(i) for i in ids]
        except ValueError:
            return HttpResponseForbidden("IDs inválidos.")
        validos = list(
            Servicio.objects.filter(pk__in=ids_int, activo=True).values_list("pk", flat=True)
        )
        prov.servicios.set(validos)
        emitir(EventoPortavoz(
            tipo="proveedor.servicios_actualizados",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"proveedor_id": prov.pk, "total": len(validos)},
        ))
        messages.success(request, f"Productos del proveedor «{prov.razon_social}» actualizados.")
        return redirect("catalogo-proveedor-detalle", pk=prov.pk)

    asignados_ids = set(prov.servicios.values_list("pk", flat=True))
    servicios = (
        Servicio.objects.filter(activo=True)
        .select_related("categoria")
        .order_by("categoria__orden", "nombre")
    )
    # Agrupado por categoría para una UI más legible.
    por_categoria: dict[str, list] = {}
    for s in servicios:
        por_categoria.setdefault(s.categoria.nombre, []).append({
            "id": s.pk, "nombre": s.nombre, "marcado": s.pk in asignados_ids,
        })
    grupos = [{"categoria": k, "items": v} for k, v in por_categoria.items()]
    return render(request, "catalogo/proveedor_servicios.html", {
        "proveedor": prov,
        "grupos": grupos,
        "total_marcados": len(asignados_ids),
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


@require_http_methods(["GET", "POST"])
def proveedor_eliminar(request, pk: int):
    """Borrado PERMANENTE de un proveedor (≠ archivar). S-LC-Feedback-V13.

    Sin FK PROTECT: ProyectoProducto.proveedor es SET_NULL y la M2M con
    Servicio se limpia sola. Informamos cuántos vínculos a productos se
    desharán. GET HTMX → modal de confirmación; POST → borra.
    """
    if (r := _gate(request, "eliminar")) is not None:
        return r
    prov = get_object_or_404(Proveedor, pk=pk)
    es_htmx = request.headers.get("HX-Request") == "true"
    ctx = {"proveedor": prov, "usos_servicios": prov.servicios.count()}
    if request.method == "POST":
        nombre = prov.razon_social
        emitir(EventoPortavoz(
            tipo="proveedor.eliminado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"proveedor_id": prov.pk, "razon_social": nombre},
        ))
        prov.delete()
        messages.success(request, f"Proveedor «{nombre}» eliminado permanentemente.")
        if es_htmx:
            return HttpResponse(status=204, headers={"HX-Redirect": reverse("catalogo-proveedores")})
        return redirect("catalogo-proveedores")
    if es_htmx:
        return render(request, "catalogo/_modal_eliminar_proveedor.html", ctx)
    return redirect("catalogo-proveedor-detalle", pk=prov.pk)


# ── Categorías CORE de proveedor (LC 2026-07) ────────────────────────────────

@require_http_methods(["GET"])
def categorias_proveedor_lista(request):
    """Las 6 categorías core del proveedor (con sus subcategorías). Editar
    nombre + color (que heredan las subcategorías). Gated por gestionar_categorias."""
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    from .models import CategoriaProveedor
    cats = CategoriaProveedor.objects.prefetch_related("subcategorias").order_by("orden", "nombre")
    return render(request, "catalogo/categorias_proveedor.html", {"categorias": cats})


@require_http_methods(["GET", "POST"])
def categoria_proveedor_editar(request, pk: int):
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    from .models import CategoriaProveedor
    cat = get_object_or_404(CategoriaProveedor, pk=pk)
    if request.method == "POST":
        form = CategoriaProveedorForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="catalogo.categoria_proveedor_actualizada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"categoria_id": cat.pk, "nombre": cat.nombre, "color": cat.color},
            ))
            messages.success(request, f"Categoría «{cat.nombre}» actualizada.")
            return redirect("catalogo-categorias-proveedor")
    else:
        form = CategoriaProveedorForm(instance=cat)
    return render(request, "catalogo/categoria_proveedor_form.html", {"form": form, "categoria": cat})


def _slug_subcategoria(nombre: str, exclude_pk: int | None = None) -> str:
    """Slug único para una SubcategoriaProveedor (autogenerado, no visible)."""
    from django.utils.text import slugify
    base = slugify(nombre)[:80] or "subcategoria"
    slug = base
    i = 2
    qs = SubcategoriaProveedor.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base[:85]}-{i}"
        i += 1
    return slug


@require_http_methods(["GET", "POST"])
def subcategoria_proveedor_nueva(request):
    """Alta de subcategoría de proveedor (LC #164 — CRUD de las 19 subcats).
    Gated por gestionar_categorias. Hereda el color de su categoría core."""
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    inicial = {}
    cat_id = request.GET.get("categoria")
    if cat_id and cat_id.isdigit():
        inicial["categoria"] = cat_id
    if request.method == "POST":
        form = SubcategoriaProveedorForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.slug = _slug_subcategoria(sub.nombre)
            sub.save()
            emitir(EventoPortavoz(
                tipo="catalogo.subcategoria_proveedor_creada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"subcategoria_id": sub.pk, "nombre": sub.nombre,
                         "categoria": sub.categoria.nombre},
            ))
            messages.success(request, f"Subcategoría «{sub.nombre}» creada.")
            return redirect("catalogo-categorias-proveedor")
    else:
        form = SubcategoriaProveedorForm(initial=inicial)
    return render(request, "catalogo/subcategoria_proveedor_form.html",
                  {"form": form, "modo": "nueva"})


@require_http_methods(["GET", "POST"])
def subcategoria_proveedor_editar(request, pk: int):
    """Edición de subcategoría: nombre, categoría, orden y activa/inactiva.
    El slug se conserva estable (no se regenera al renombrar)."""
    if (r := _gate(request, "gestionar_categorias")) is not None:
        return r
    sub = get_object_or_404(SubcategoriaProveedor, pk=pk)
    if request.method == "POST":
        form = SubcategoriaProveedorForm(request.POST, instance=sub)
        if form.is_valid():
            form.save()  # slug no está en el form → se mantiene el existente
            emitir(EventoPortavoz(
                tipo="catalogo.subcategoria_proveedor_actualizada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"subcategoria_id": sub.pk, "nombre": sub.nombre,
                         "activa": sub.activa},
            ))
            messages.success(request, f"Subcategoría «{sub.nombre}» actualizada.")
            return redirect("catalogo-categorias-proveedor")
    else:
        form = SubcategoriaProveedorForm(instance=sub)
    return render(request, "catalogo/subcategoria_proveedor_form.html",
                  {"form": form, "modo": "editar", "subcategoria": sub})


# ── Imagen de producto (Drive) — pegar/subir (LC 2026-07) ────────────────────

@require_http_methods(["POST"])
def servicio_imagen(request, pk: int):
    """Sube (o reemplaza) la imagen del producto a Drive (subcarpeta «Productos»).
    Acepta un archivo `imagen` (de <input> o del portapapeles). Devuelve JSON.
    Gated por `catalogo.editar`. Fallback gracioso si Drive falla."""
    if (r := _gate(request, "editar")) is not None:
        return r
    from django.http import JsonResponse
    srv = get_object_or_404(Servicio, pk=pk)
    archivo = request.FILES.get("imagen")
    if not archivo:
        return JsonResponse({"ok": False, "error": "No llegó ninguna imagen."}, status=400)
    from lib.adjuntos import subir
    res = subir(archivo, subcarpeta="Productos")
    if not res.ok:
        return JsonResponse({"ok": False, "error": res.error})
    srv.imagen_file_id = res.data.get("id", "")
    srv.imagen_url = res.data.get("webViewLink", "") or res.data.get("thumbnailLink", "")
    srv.save(update_fields=["imagen_file_id", "imagen_url", "actualizado_en"])
    emitir(EventoPortavoz(
        tipo="catalogo.servicio_imagen",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"servicio_id": srv.pk, "file_id": srv.imagen_file_id},
    ))
    return JsonResponse({"ok": True, "url": srv.imagen_url, "file_id": srv.imagen_file_id})
