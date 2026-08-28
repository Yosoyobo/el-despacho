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

import contextlib
import json
from decimal import Decimal

from django.contrib import messages
from django.db.models import Case, DecimalField, F, Value, When
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from lib.busqueda import q_texto
from lib.navegacion import destino_de_regreso
from lib.permisos import puede
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from . import procesos as procesos_default
from .forms import (
    CategoriaForm,
    CategoriaProveedorForm,
    ProveedorForm,
    ServicioForm,
    SubcategoriaProveedorForm,
)
from .models import (
    CategoriaProveedor,
    CategoriaServicio,
    Proveedor,
    Servicio,
    SubcategoriaProveedor,
)


def _proveedores_activos():
    """Proveedores activos para los selects de impresión / procesos."""
    return list(Proveedor.objects.filter(activo=True).order_by("razon_social"))


def _ids_proveedores_del_post(post) -> list[int]:
    """Ids de proveedor que trae el POST, **en el orden en que llegaron** y
    filtrados contra los ACTIVOS (LC 2026-08-22, nota 2).

    El orden importa: el primero es el que queda como principal, y
    `Proveedor.Meta.ordering` es alfabético — «el primero de la M2M» no es «el
    primero que marcaste». Nunca se confía en los ids del cliente: lo que no
    exista o esté archivado se descarta en silencio.
    """
    pedidos: list[int] = []
    for crudo in post.getlist("proveedores"):
        crudo = (crudo or "").strip()
        if crudo.isdigit() and int(crudo) not in pedidos:
            pedidos.append(int(crudo))
    if not pedidos:
        return []
    validos = set(
        Proveedor.objects.filter(activo=True, pk__in=pedidos).values_list("pk", flat=True)
    )
    return [pk for pk in pedidos if pk in validos]


def _ctx_calculadora(srv=None, post=None) -> dict:
    """Contexto del recuadro de la calculadora — el MISMO en el alta y en la ficha.

    `mostrar_calculadora` = ya aplica (el producto trae el proveedor, se pinta
    visible). `calc_disponible` = el recuadro se pinta —escondido si aún no
    aplica— porque el proveedor que la dispara EXISTE, así que el JS puede
    revelarlo en cuanto se marque (LC 2026-08-22, nota 3).
    """
    from ajustes.models.fiscal import ConfiguracionFiscal

    from .calculadora import (
        FACTOR_DEFAULT,
        calcular,
        parsear_detalles,
        proveedores_calculadora,
        servicio_usa_calculadora,
    )
    mostrar = servicio_usa_calculadora(srv) if srv is not None and srv.pk else False
    ids = proveedores_calculadora()
    # Con `post` (un alta que no pasó validación) se re-pintan los insumos que se
    # acababan de capturar; sin él, lo guardado.
    det = parsear_detalles(post) if post is not None else ((srv.detalles_costo or {}) if srv is not None else {})

    def _pad4(lst):
        return (list(lst or []) + ["", "", "", ""])[:4]

    def _disp(v):
        return "" if (not v or str(v) in {"0", "0.0", "0.00"}) else str(v)

    iva_tasa = ConfiguracionFiscal.obtener().iva_tasa
    resultado = calcular(det, iva_tasa) if mostrar else None
    return {
        "mostrar_calculadora": mostrar,
        "calc_disponible": mostrar or bool(ids),
        "calc_proveedores_json": json.dumps([str(i) for i in ids]),
        "calc_factor": str((resultado or {}).get("factor") or FACTOR_DEFAULT),
        "calc_materiales": [_disp(x) for x in _pad4(det.get("materiales"))],
        "calc_sublimacion": [_disp(x) for x in _pad4(det.get("sublimacion"))],
        "calc_mano_obra": _disp(det.get("mano_obra")),
        "calc_resultado": resultado,
        "iva_tasa": iva_tasa,
    }


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

    from django.db.models import Count

    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    incluir_archivados = request.GET.get("archivados") == "1" and puede_archivar
    qs = (
        Servicio.objects.select_related("categoria", "proveedor_principal")
        .prefetch_related("proveedores")
        .annotate(usos_count=Count("en_proyectos", distinct=True))
    )
    # LC 2026-08-12: la ficha muestra la foto del producto MÁS las propias de
    # sus usos. Un `Prefetch` acotado a las que tienen foto = UNA consulta
    # extra en total, no una por producto.
    from apps.los_proyectos.models import ProyectoProducto
    from django.db.models import Prefetch

    qs = qs.prefetch_related(Prefetch(
        "en_proyectos",
        queryset=ProyectoProducto.objects.exclude(imagen_file_id="")
        .only("id", "servicio_id", "imagen_file_id")
        .order_by("-creado_en"),
        to_attr="usos_con_foto",
    ))
    # `activo` sigue siendo el mecanismo de ARCHIVADO (se conserva); solo se
    # jubiló su presentación como "Disponible/No disponible" (#10).
    if not incluir_archivados:
        qs = qs.filter(activo=True)
    if q:
        # LC 2026-07-25: el buscador también encuentra por PROVEEDOR (escribes
        # "Plymouth" y salen sus productos). `distinct` porque el join M2M
        # duplicaría filas cuando varios proveedores hacen match.
        # LC 2026-07-26 (Oscar): y por los ALIAS con los que se vendió en algún
        # proyecto («TShirt Modelo Janet» encuentra la playera del catálogo) —
        # los alias son parte de la base buscable de productos.
        qs = qs.filter(q_texto(
            q, "nombre", "proveedores__razon_social",
            "en_proyectos__nombre_proyecto")).distinct()
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    # Sprint 2 UX (item 6): orden por Categoría con toggle asc/desc; el default
    # es alfabético por nombre (estable). El whitelist evita order_by arbitrario.
    #
    # LC 2026-08-13 (Oscar): «agregar arriba un filtro de ordenar por nombre,
    # núm. de usos, costo, precio y markup». No es una columna de la base (es
    # una propiedad), así que se calcula en SQL para poder ordenar. Tiene que
    # medir LO MISMO que `Servicio.margen_porcentaje`: (precio − costo) / costo
    # × 100, y sin costo capturado vale 0.
    qs = qs.annotate(margen_calc=Case(
        When(costo__gt=0,
             then=(F("precio_base") - F("costo")) * Value(Decimal("100")) / F("costo")),
        default=Value(Decimal("0")),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    ))
    _campo_orden = {
        "nombre": "nombre",
        "categoria": "categoria__nombre",
        "usos": "usos_count",
        "costo": "costo",
        "precio": "precio_base",
        "margen": "margen_calc",
    }
    orden = (request.GET.get("orden") or "").strip()
    _clave = orden.lstrip("-")
    if _clave in _campo_orden:
        campo = _campo_orden[_clave]
        qs = qs.order_by(("-" if orden.startswith("-") else "") + campo, "nombre")
    else:
        orden = ""
        qs = qs.order_by("nombre")
    # Pastillas de ordenamiento del encabezado (el `-` alterna asc/desc).
    ordenamientos = [
        {"clave": "nombre", "label": "Nombre"},
        {"clave": "usos", "label": "Usos"},
    ]
    if ve_precios:
        ordenamientos += [
            {"clave": "costo", "label": "Costo"},
            {"clave": "precio", "label": "Precio"},
            {"clave": "margen", "label": "Markup"},
        ]
    for o in ordenamientos:
        o["activo"] = _clave == o["clave"]
        # Si ya está activa ascendente, el siguiente clic la invierte.
        o["orden"] = ("-" if (o["activo"] and not orden.startswith("-")) else "") + o["clave"]
        o["flecha"] = "↓" if (o["activo"] and orden.startswith("-")) else "↑"
    # LC revisión buzón R2: modo edición inline (celdas editables) opt-in.
    editar_inline = request.GET.get("editar") == "1" and puede_editar
    # LC 2026-08-12 (Oscar): «la página de productos la vamos a formatear por
    # default en vista de fichas, como la de proveedores. La tabla de edición
    # rápida se mantiene como opción.» La edición rápida implica tabla.
    vista = (request.GET.get("vista") or "").strip()
    en_tarjetas = vista != "tabla" and not editar_inline
    # #12 unidad consolidada a 'pz' (columna retirada) · #9 columna "Usos"
    # (veces que el producto ha aparecido en proyectos) · #10 sin "Estado".
    # Sprint 2 UX: Categoría ordenable (item 6) · Proveedores al 3er lugar (item 11).
    cabeceras = [
        {"label": "Nombre"},
        {"label": "Categoría", "sort_key": "categoria"},
        {"label": "Proveedores"},
        {"label": "Usos", "align": "right"},
    ]
    if ve_precios:
        cabeceras.append({"label": "Costo", "align": "right"})
        cabeceras.append({"label": "Precio", "align": "right"})
        # LC 2026-08-28: la columna mide MARKUP (lo que se le suma al costo),
        # no margen sobre el precio. Se llama distinto para que no haya dos
        # cosas con el mismo nombre y fórmulas distintas.
        cabeceras.append({"label": "Markup", "align": "right"})
    # `puede_crear` también: la fila trae el botón de duplicar, y una celda
    # sin su cabecera descuadra la tabla entera.
    if editar_inline or puede_editar or puede_archivar or puede_eliminar or puede_crear:
        cabeceras.append({"label": "", "align": "right"})
    # querystring_base: preserva filtros al cambiar el orden (item 6).
    from urllib.parse import urlencode
    _params = []
    if q:
        _params.append(("q", q))
    if categoria_id:
        _params.append(("categoria", categoria_id))
    if incluir_archivados:
        _params.append(("archivados", "1"))
    if editar_inline:
        _params.append(("editar", "1"))
    if vista == "tabla":
        _params.append(("vista", "tabla"))
    querystring_base = urlencode(_params)
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
        "ordenamientos": ordenamientos,
        "orden_actual": orden,
        "querystring_base": querystring_base,
        "editar_inline": editar_inline,
        "en_tarjetas": en_tarjetas,
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
        destino = destino_de_regreso(request, reverse("catalogo-lista"))
        if es_htmx:
            return HttpResponse(status=204, headers={"HX-Redirect": destino})
        return redirect(destino)
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
            # LC 2026-07-25: impresión + procesos adicionales (plantilla).
            srv.procesos_default = procesos_default.parsear(request.POST)
            srv.save()
            form.save_m2m()  # persiste proveedores marcados (antes se perdían)
            # LC 2026-08-22 (nota 4): el alta deja el producto COMPLETO. Si se
            # marcaron proveedores y nadie eligió principal, el primero que se
            # marcó lo es. `proveedor_default` ya caía al primero ACTIVO de la
            # M2M —que es el primero alfabético—, así que dejarlo explícito es
            # lo que hace que el ★ coincida con lo que el usuario eligió.
            if srv.proveedor_principal_id is None:
                ids_prov = _ids_proveedores_del_post(request.POST)
                ligados = set(srv.proveedores.values_list("pk", flat=True))
                primero = next((pk for pk in ids_prov if pk in ligados), None)
                if primero is not None:
                    srv.proveedor_principal_id = primero
                    srv.save(update_fields=["proveedor_principal", "actualizado_en"])
            # LC 2026-08-22 (nota 3): la calculadora también corre en el ALTA.
            # Antes sólo se guardaba al editar, así que capturar los insumos en
            # el alta no servía de nada: el primer guardado los tiraba. Va
            # DESPUÉS de `save_m2m()` porque el gating depende de la M2M.
            from apps.el_catalogo.calculadora import (
                calcular,
                parsear_detalles,
                servicio_usa_calculadora,
            )
            if servicio_usa_calculadora(srv):
                srv.detalles_costo = parsear_detalles(request.POST)
                srv.costo = calcular(srv.detalles_costo)["subtotal"]
                srv.save(update_fields=["detalles_costo", "costo", "actualizado_en"])
            emitir(EventoPortavoz(
                tipo="catalogo.servicio_creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk, "nombre": srv.nombre, "categoria": srv.categoria.nombre},
            ))
            messages.success(request, f"Producto «{srv.nombre}» creado.")
            # LC 2026-07-25 (Oscar): al crear se abre la PÁGINA DEL PRODUCTO
            # (para seguir con imagen, procesos, proveedores), no la lista.
            destino = reverse("catalogo-editar", args=[srv.pk])
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
        # inválido → cae al render (modal si es HTMX).
    else:
        form = ServicioForm()
    ctx = {
        "form": form, "modo": "nuevo",
        "precio_readonly": not puede(request.user, "catalogo", "editar_precios"),
        "ve_precios": puede(request.user, "catalogo", "ver_precios"),
        # Impresión + procesos adicionales (la página completa los captura; el
        # modal de alta rápida sigue ligero — se capturan al abrir el producto).
        "proveedores_activos": _proveedores_activos(),
        "procesos_default_json": json.dumps(
            procesos_default.parsear(request.POST) if request.method == "POST" else []
        ),
        # LC 2026-08-22 (nota 3): el recuadro de la calculadora se pinta ESCONDIDO
        # y el JS lo revela en cuanto se marca el proveedor que la dispara.
        **_ctx_calculadora(post=request.POST if request.method == "POST" else None),
        # LC 2026-08-22 (nota 11): saltar de una categoría a otra sin volver a la
        # lista — las pastillas llevan a la lista ya filtrada.
        "categorias_navegacion": CategoriaServicio.objects.filter(activa=True),
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
    # LC 2026-08-12: sin `?desde=`, el «← Volver» respeta el `?volver=` con el
    # que llegaste desde la lista, así que regresas con tus filtros puestos.
    if not back_url:
        from lib.navegacion import es_ruta_interna
        crudo = (request.GET.get("volver") or "").strip()
        if es_ruta_interna(crudo):
            back_url = crudo
    return {"breadcrumb_trail": trail, "back_url_producto": back_url}


@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    if (r := _gate(request, "editar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    puede_editar_precios = puede(request.user, "catalogo", "editar_precios")
    # El costo ANTES de tocar nada: con él se decide qué líneas de proyecto lo
    # traían copiado del catálogo y cuáles se negociaron aparte (Bug D §14 —
    # `form.is_valid()` ya habría escrito el nuevo sobre `srv`).
    srv_costo_previo = srv.costo
    if request.method == "POST":
        form = ServicioForm(request.POST, instance=srv)
        if form.is_valid():
            obj = form.save(commit=False)
            # Si no tiene editar_precios, restauramos el precio original.
            if not puede_editar_precios:
                obj.precio_base = srv.precio_base
            # LC 2026-07-25: impresión + procesos adicionales (plantilla). Solo
            # se reescriben si el form los mandó — un POST sin el campo (otro
            # flujo) NO debe borrar lo capturado.
            if "procesos_default_json" in request.POST:
                obj.procesos_default = procesos_default.parsear(request.POST)
            # LC 2026-07-26 (Oscar, ronda 3): quitar la foto en esta página es un
            # cambio PENDIENTE hasta que se aprieta «Guardar producto» — salirse
            # sin guardar ya no la desliga. El archivo NO se borra de Drive:
            # puede estar congelado en una cotización enviada.
            if request.POST.get("imagen_quitar") == "1":
                obj.imagen_file_id = ""
                obj.imagen_url = ""
            obj.save()
            form.save_m2m()  # persiste proveedores marcados (antes se perdían)
            # Calculadora de costos (proveedores como Simil Cuero Plymouth): si el
            # producto la usa, guardamos los insumos y el Subtotal (antes de IVA)
            # alimenta el COSTO del producto (el precio de venta lo pone el usuario).
            from apps.el_catalogo.calculadora import (
                calcular,
                parsear_detalles,
                servicio_usa_calculadora,
            )
            costo_anterior = srv_costo_previo
            if servicio_usa_calculadora(obj):
                obj.detalles_costo = parsear_detalles(request.POST)
                obj.costo = calcular(obj.detalles_costo)["subtotal"]
                obj.save(update_fields=["detalles_costo", "costo", "actualizado_en"])
            # LC 2026-08-12 (Oscar): el costo nuevo baja SOLO a los proyectos
            # vivos — los que no han generado egreso ni cerrado, y donde nadie
            # escribió un costo aparte. Lo pagado o facturado no se toca.
            from apps.el_catalogo.propagacion import propagar_costo
            tocadas = propagar_costo(obj, costo_anterior, request.user)
            if tocadas:
                messages.info(
                    request,
                    f"El costo nuevo se aplicó a {tocadas} línea"
                    f"{'s' if tocadas != 1 else ''} de proyectos abiertos.",
                )
            emitir(EventoPortavoz(
                tipo="catalogo.servicio_actualizado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"servicio_id": srv.pk},
            ))
            messages.success(request, "Producto actualizado.")
            # LC 2026-08-12 (Oscar): «al darle guardar me saca a la lista».
            # Guardar recarga la MISMA ficha; para salir están el «← Volver» y
            # la miga, que siguen respetando de dónde venías (`?desde=`,
            # `?volver=`) — por eso se conserva la query string.
            destino = reverse("catalogo-editar", args=[srv.pk])
            cola = request.META.get("QUERY_STRING", "")
            return redirect(f"{destino}?{cola}" if cola else destino)
    else:
        form = ServicioForm(instance=srv)
    # Sprint 2 UX (item 7): el detalle y la edición se unifican en este panel;
    # abajo mostramos el historial de usos (solo lectura).
    usos = (
        srv.en_proyectos
        .select_related("servicio", "proyecto", "proyecto__cliente", "variacion", "proveedor")
        .prefetch_related("procesos__proveedor")
        .order_by("-creado_en")
    )
    return render(request, "catalogo/form.html", {
        "form": form, "modo": "editar", "servicio": srv,
        "precio_readonly": not puede_editar_precios,
        "usos": usos,
        "ve_precios": puede(request.user, "catalogo", "ver_precios"),
        # LC 2026-08-22 (nota 10): la ficha ya trae archivar y eliminar al pie —
        # antes había que volver a la lista para cualquiera de las dos.
        "puede_archivar": puede(request.user, "catalogo", "archivar"),
        "puede_eliminar": puede(request.user, "catalogo", "eliminar"),
        # Duplicar es crear: pide el mismo permiso que dar de alta un producto.
        "puede_crear": puede(request.user, "catalogo", "crear"),
        # Calculadora de costos (Simil Cuero Plymouth): prefill + resultado en vivo.
        **_ctx_calculadora(srv),
        # LC 2026-07-25: impresión + procesos adicionales del producto (plantilla
        # que se copia al proyecto). El JSON alimenta el JS del recuadro.
        "proveedores_activos": _proveedores_activos(),
        "procesos_default_json": json.dumps(procesos_default.normalizados(srv)),
        "procesos_costo_extra": procesos_default.costo_extra(srv),
        # LC 2026-08-22 (nota 11): navegación entre categorías desde la ficha.
        "categorias_navegacion": CategoriaServicio.objects.filter(activa=True),
        **_navegacion_producto(request),
    })


@require_http_methods(["POST"])
def duplicar(request, pk: int):
    """Clona el producto con todo lo suyo y abre la copia para renombrarla.

    LC 2026-08-28 (Oscar): «Duplicar producto tiene que existir. Y llevarse
    absolutamente todos los datos.» Qué viaja y qué no está en
    `apps.el_catalogo.duplicar`.

    Se pide el permiso de CREAR (que es lo que hace) y el de ver el original.
    """
    if (r := _gate(request, "crear")) is not None:
        return r
    from .duplicar import duplicar_servicio
    origen = get_object_or_404(Servicio, pk=pk)
    copia = duplicar_servicio(origen, actor=request.user)
    messages.success(
        request,
        f"Se duplicó «{origen.nombre}». Ponle su nombre a la copia y guárdala.",
    )
    return redirect(reverse("catalogo-editar", args=[copia.pk]))


@require_http_methods(["POST"])
def archivar(request, pk: int):
    if (r := _gate(request, "archivar")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    srv.activo = not srv.activo
    srv.save(update_fields=["activo", "actualizado_en"])
    messages.success(request, "Producto " + ("archivado." if not srv.activo else "reactivado."))
    return redirect(destino_de_regreso(request, reverse("catalogo-lista")))


# ── Usos (bitácora histórica del producto) ───────────────────────────────────
# Sprint Fiscal 2026-07 (#8): la vieja página de "Variaciones" (sub-catálogo
# manual) pasa a ser una bitácora de USOS derivada del historial real: cada vez
# que el producto se usó en un proyecto, con su costo, precio, proveedor,
# impresión y procesos extras. Solo lectura. El modelo Variacion se conserva
# (proyectos/cotizaciones lo siguen usando); ya no se crea/edita desde aquí.

def usos_lista(request, pk: int):
    """Bitácora histórica de usos del producto en proyectos (solo lectura)."""
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    srv = get_object_or_404(Servicio, pk=pk)
    ve_precios = puede(request.user, "catalogo", "ver_precios")
    usos = (
        srv.en_proyectos
        .select_related("servicio", "proyecto", "proyecto__cliente", "variacion", "proveedor")
        .prefetch_related("procesos__proveedor")
        .order_by("-creado_en")
    )
    return render(request, "catalogo/usos.html", {
        "servicio": srv,
        "usos": usos,
        "ve_precios": ve_precios,
        "puede_editar": puede(request.user, "catalogo", "editar"),
    })


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


# ── Quick-create de Servicio (S-LC-Feedback-V2) ─────────────────────────────

@require_http_methods(["POST"])
def servicio_quick_create(request):
    """POST /catalogo/quick-create/ — crea Servicio inline desde el form de Proyecto.

    Espera POST con: nombre, categoria_id, precio_base, costo y `proveedores`
    (0..n ids). Retorna JSON con id + nombre + categoria_nombre + precio +
    proveedores para que el JS del form de Proyecto agregue la opción al select,
    la seleccione y pinte la etiqueta del proveedor.

    LC 2026-08-22 (nota 2): antes el atajo sólo aceptaba nombre/categoría/precio/
    costo, así que el producto nacía **sin proveedor** — y sin proveedor no hay
    calculadora (`servicio_usa_calculadora` pregunta por la M2M) ni principal.
    De ahí que «el alta rápida deje el producto a medias».
    """
    if (r := _gate(request, "crear")) is not None:
        return r
    from django.http import JsonResponse
    nombre = (request.POST.get("nombre") or "").strip()
    categoria_id = request.POST.get("categoria_id")
    precio_raw = (request.POST.get("precio_base") or "").strip()
    costo_raw = (request.POST.get("costo") or "0").strip() or "0"
    # #12: unidad consolidada a 'pz' (no hay selector; se ignora lo que llegue).
    unidad = "pz"
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
    # Proveedores: el PRIMERO que se marcó queda como principal, así el ★ del
    # catálogo dice la verdad desde el minuto uno y la tarjeta del proyecto
    # autocompleta al proveedor correcto (nota 4).
    ids_prov = _ids_proveedores_del_post(request.POST)
    s = Servicio.objects.create(
        nombre=nombre,
        categoria=categoria,
        precio_base=precio,
        costo=costo,
        unidad=unidad,
        proveedor_principal_id=ids_prov[0] if ids_prov else None,
        creado_por=request.user,
    )
    if ids_prov:
        s.proveedores.set(ids_prov)
    provs = list(Proveedor.objects.filter(pk__in=ids_prov)) if ids_prov else []
    por_pk = {pv.pk: pv for pv in provs}
    principal = por_pk.get(ids_prov[0]) if ids_prov else None
    emitir(EventoPortavoz(
        tipo="catalogo.servicio_quick_creado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"servicio_id": s.pk, "nombre": s.nombre, "categoria": categoria.nombre,
                 "proveedores": ids_prov},
    ))
    return JsonResponse({
        "ok": True,
        "id": s.pk,
        "nombre": s.nombre,
        "categoria_nombre": categoria.nombre,
        "categoria_id": str(categoria.pk),
        "precio": str(s.precio_base),
        "costo": str(s.costo),
        "margen": s.margen_porcentaje,
        "label": f"{s.nombre} ({categoria.nombre})",
        # Para que el JS pinte la etiqueta y la tarjeta del proyecto autocomplete
        # el proveedor sin recargar (nota 2).
        "proveedores": [{"id": pk, "razon_social": por_pk[pk].razon_social}
                        for pk in ids_prov if pk in por_pk],
        "proveedor_id": str(principal.pk) if principal else "",
        "proveedor": principal.razon_social if principal else "",
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
        qs = qs.filter(q_texto(
            q, "razon_social", "nombre_contacto", "email_contacto", "telefono",
            "subcategorias__nombre", "subcategorias__categoria__nombre",
            "servicios__nombre", "productos_proyecto__proyecto__codigo",
            "productos_proyecto__proyecto__nombre",
        ))
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


def proveedor_buscar(request):
    """Autocomplete de proveedores para el disparador @ en gastos/procesos del
    proyecto (ticket UX 2026-07). GET ?q=<prefijo> → {resultados:[{id,nombre}]}.
    Solo requiere sesión: los nombres de proveedor ya se exponen en la tarjeta
    de producto (select de impresión) a quien edita el proyecto."""
    from django.http import JsonResponse
    if not getattr(request.user, "is_authenticated", False):
        return HttpResponseForbidden("No autenticado.")
    q = (request.GET.get("q") or "").strip()
    qs = Proveedor.objects.filter(activo=True)
    if q:
        qs = qs.filter(q_texto(q, "razon_social"))
    qs = qs.order_by("razon_social")[:8]
    return JsonResponse({"resultados": [
        {"id": p.pk, "nombre": p.razon_social} for p in qs
    ]})


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
            # LC 2026-08-12: se abre SU ficha, igual que un producto nuevo —
            # es lo que quieres hacer enseguida (ligarle productos, ubicación).
            destino = reverse("catalogo-proveedor-detalle", args=[prov.pk])
            if es_htmx:
                return HttpResponse(status=204, headers={"HX-Redirect": destino})
            return redirect(destino)
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
    # Proyectos donde el proveedor está involucrado — asignado formalmente o
    # porque surte un producto del proyecto.
    #
    # Oscar 2026-07-25: aquí va el HISTORIAL COMPLETO, no sólo lo vigente.
    # Antes se excluían los cerrados/cancelados y el manager `activos` dejaba
    # fuera los archivados, así que en cuanto un proyecto se entregaba
    # desaparecía de la ficha del proveedor y ya no había dónde consultarlo.
    from apps.los_proyectos.models import Proyecto as _Proyecto
    from django.db.models import Q as _Q
    proyectos_involucrados = (
        _Proyecto.objects
        .filter(_Q(proveedores_asignados__proveedor=prov) | _Q(productos__proveedor=prov))
        .select_related("cliente")
        .distinct().order_by("-creado_en")[:100]
    )

    from papeleo.ligado import contexto_ficha

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
        # Su papeleo (cotizaciones que mandó, comprobantes sin CFDI). Sale de
        # nuestra base, así que la ficha se pinta igual si el archivo está caído.
        **contexto_ficha(request.user, prov),
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
    return redirect(destino_de_regreso(request, reverse("catalogo-proveedores")))


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

    # LC 2026-07-26 (Oscar): tecla Delete sobre el recuadro = desligar la foto.
    # El archivo NO se borra de Drive: el mismo file_id puede estar congelado en
    # cotizaciones ya enviadas y borrarlo dejaría huecos en esos documentos.
    if (request.POST.get("quitar") or "") == "1":
        if not (srv.imagen_file_id or "").strip():
            return JsonResponse({"ok": False, "error": "Este producto no tiene foto."}, status=400)
        srv.imagen_file_id = ""
        srv.imagen_url = ""
        srv.save(update_fields=["imagen_file_id", "imagen_url", "actualizado_en"])
        emitir(EventoPortavoz(
            tipo="catalogo.servicio_imagen",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"servicio_id": srv.pk, "file_id": "", "quitada": True},
        ))
        return JsonResponse({"ok": True, "quitada": True, "destino": "catalogo",
                             "file_id": "", "url": "",
                             "mensaje": "✓ Se quitó la foto del producto."})

    archivo = request.FILES.get("imagen")
    if not archivo:
        return JsonResponse({"ok": False, "error": "No llegó ninguna imagen."}, status=400)
    from lib import almacen
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
    # `imagen_url` de Drive es una PÁGINA, no una imagen: la miniatura se sirve
    # por el proxy autenticado.
    return JsonResponse({
        "ok": True,
        "file_id": srv.imagen_file_id,
        "url": almacen.url(srv.imagen_file_id),
        "destino": "catalogo",
        "mensaje": "✓ Foto guardada en el producto del catálogo.",
    })


def _es_imagen_de_producto(file_id: str) -> bool:
    """True si el `file_id` es la foto de un producto del catálogo, de un uso en
    un proyecto o de una línea de cotización.

    Es el candado que evita que un enlace sirva para leer archivos arbitrarios
    de Drive (mismo criterio para el proxy autenticado y el enlace firmado).
    """
    if not file_id:
        return False
    # LC 2026-08-12: eran hasta TRES consultas por cada imagen de la pantalla.
    # El veredicto no cambia (el `file_id` es inmutable), así que se recuerda.
    from django.core.cache import cache
    clave = f"catalogo:img_ok:{file_id}"
    try:
        recordado = cache.get(clave)
    except Exception:  # noqa: BLE001 — Redis caído: se consulta como siempre
        recordado = None
    if recordado is not None:
        return bool(recordado)
    veredicto = _consultar_si_es_imagen_de_producto(file_id)
    with contextlib.suppress(Exception):
        cache.set(clave, veredicto, 86400 if veredicto else 60)
    return veredicto


def _consultar_si_es_imagen_de_producto(file_id: str) -> bool:
    if Servicio.objects.filter(imagen_file_id=file_id).exists():
        return True
    try:
        from apps.los_proyectos.models import ProyectoProducto
        if ProyectoProducto.objects.filter(imagen_file_id=file_id).exists():
            return True
    except Exception:  # noqa: BLE001 — app no instalada en este proyecto Django
        pass
    try:
        from apps.cotizaciones.models import CotizacionItem
        if CotizacionItem.objects.filter(imagen_file_id=file_id).exists():
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _bytes_de_imagen(file_id: str, mini: bool = False):
    """`(contenido, mime)` de la imagen, de El Almacén.

    S-Medios-V1: lee del disco. Si la llave todavía no está guardada (una foto
    que subió Drive antes de este sprint y que la importación no ha alcanzado),
    `almacen.leer` la baja de Drive UNA vez y la deja guardada con sus derivados
    — de ahí en adelante la sirve El Portero y esta vista no vuelve a entrar.
    """
    from lib import almacen

    ruta = almacen.ruta_variante(file_id, "w400" if mini else "w1000")
    if ruta is not None and ruta.is_file():
        return ruta.read_bytes(), ("image/png" if ruta.suffix == ".png" else "image/jpeg")
    try:
        contenido, mime, _ = almacen.leer(file_id)
    except almacen.ArchivoNoDisponible:
        return None
    # Recién importada: ya tiene derivados, así que se sirve el que se pidió.
    ruta = almacen.ruta_variante(file_id, "w400" if mini else "w1000")
    if ruta is not None and ruta.is_file():
        return ruta.read_bytes(), ("image/png" if ruta.suffix == ".png" else "image/jpeg")
    # Sin derivado posible (formato que Pillow no abre): el original tal cual,
    # que es exactamente lo que hacía el proxy antes de este sprint.
    return contenido, mime


@require_http_methods(["GET"])
def imagen_producto(request, file_id: str):
    """Camino FRÍO de la foto de un producto (miniaturas y previews).

    Desde S-Medios-V1 las imágenes las sirve El Portero directo del disco
    (`/medios/…`, ver `lib/almacen.py`). Esta vista queda para dos casos: una
    llave que todavía no está en el almacén —la materializa al paso, así que la
    siguiente vez ya sale por el camino rápido— y una imagen sin derivado
    posible.

    Sigue autenticada y gateada por `catalogo.ver_nombres`, y sólo entrega
    archivos que sean imagen de un producto, de un uso o de una línea de
    cotización.
    """
    if (r := _gate(request, "ver_nombres")) is not None:
        return r
    if not _es_imagen_de_producto(file_id):
        return HttpResponse(status=404)
    # `?mini=1` sirve la miniatura de ~30 KB de las fichas del catálogo.
    mini = request.GET.get("mini") == "1"
    etiqueta = f'"{file_id}{"-mini" if mini else ""}"'
    # El `file_id` es inmutable: si cambia la foto, cambia el id. Así que si el
    # navegador ya la tiene, no hace falta ni leerla.
    if request.headers.get("If-None-Match") == etiqueta:
        return HttpResponse(status=304)
    datos = _bytes_de_imagen(file_id, mini=mini)
    if datos is None:
        return HttpResponse(status=404)
    resp = HttpResponse(datos[0], content_type=datos[1])
    # LC 2026-08-13 (Oscar): «¿hay manera de guardar las miniaturas en el
    # dispositivo para que carguen más rápido?». Un MES y `immutable`, así que el
    # navegador ni siquiera pregunta si cambiaron: las pinta del disco. Es seguro
    # porque el `file_id` es la identidad del archivo — al cambiar la foto cambia
    # el id, y con él la URL.
    resp["Cache-Control"] = "private, max-age=2592000, immutable"
    resp["ETag"] = etiqueta
    return resp
