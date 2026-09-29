"""Tesorería → CFDI recibidos (S-Pendientes-Sep28).

Los comprobantes que llegaron por correo y no se pudieron ligar solos. Hasta
este sprint vivían en La Gerencia → Ajustes, que es la configuración del
despacho; pero **resolverlos es operación**: decidir de qué factura es un
comprobante o registrar el gasto de un proveedor es trabajo de quien lleva la
Tesorería. Por eso la pantalla que los resuelve vive aquí y se gatea por los
permisos granulares de Tesorería y de Facturación (§4 #20), no por el de
Ajustes.

La lógica no vive en la vista: vive en `apps.facturacion.cfdi_recibidos`, que
también usan El Chalán y el modal de «Nuevo egreso». Esta vista sólo decide qué
se pinta y a quién se le deja picar qué.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from lib.permisos import puede, requiere_permiso, tiene_rol

FILTROS = ("pendiente", "ligado", "ignorado", "todos")


def _puede(user, modulo: str, accion: str) -> bool:
    """Permiso granular con el failsafe de super_admin (§4 #20)."""
    return tiene_rol(user, "super_admin") or puede(user, modulo, accion)


def puede_resolver_egresos(user) -> bool:
    return _puede(user, "tesoreria", "capturar_egreso")


def puede_ligar_facturas(user) -> bool:
    return _puede(user, "facturacion", "editar")


def puede_ignorar(user, tipo: str) -> bool:
    """Ignorar pide el permiso del lado al que pertenece el comprobante.

    Uno PROPIO (lo emitió Learning Center) es de Facturación: quien lo liga a su
    factura es quien decide que no es de nadie (`facturacion.editar`). Uno de
    PROVEEDOR es un gasto: Tesorería (`tesoreria.capturar_egreso`). Uno DUDOSO
    se puede resolver por cualquiera de los dos lados, así que cualquiera de los
    dos permisos basta para descartarlo (un duplicado, una prueba).
    """
    from apps.facturacion import cfdi_recibidos as svc

    if tipo == svc.TIPO_PROPIO:
        return puede_ligar_facturas(user)
    if tipo == svc.TIPO_PROVEEDOR:
        return puede_resolver_egresos(user)
    return puede_ligar_facturas(user) or puede_resolver_egresos(user)


def _url_lista(filtro: str = "pendiente") -> str:
    base = reverse("tesoreria:cfdi-recibidos")
    return base if filtro == "pendiente" else f"{base}?{urlencode({'estado': filtro})}"


@login_required
@requiere_permiso("tesoreria", "ver")
def cfdi_recibidos(request):
    """La lista, con lo necesario para resolver cada pendiente en su tarjeta."""
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import ESTADO_PENDIENTE, CfdiEntrante

    filtro = (request.GET.get("estado") or "pendiente").strip()
    if filtro not in FILTROS:
        filtro = "pendiente"
    qs = CfdiEntrante.objects.select_related("factura", "egreso", "proveedor")
    if filtro != "todos":
        qs = qs.filter(estado=filtro)
    cfdis = list(qs.order_by("-recibido_en")[:200])

    propio = svc.rfc_propio()
    tarjetas = []
    hay_facturas = False
    for c in cfdis:
        tipo = svc.clasificar(c, propio)
        t = {"c": c, "tipo": tipo, "que_es": svc.ETIQUETA_TIPO[tipo],
             "puede_ignorar": puede_ignorar(request.user, tipo)}
        if c.estado == ESTADO_PENDIENTE:
            if tipo in (svc.TIPO_PROVEEDOR, svc.TIPO_DUDOSO):
                prov = svc.proveedor_sugerido(c)
                t["proveedor"] = prov
                t["egresos"] = svc.egresos_que_casan(c, prov)
            if tipo in (svc.TIPO_PROPIO, svc.TIPO_DUDOSO):
                t["candidatas"] = svc.facturas_candidatas(c)
                hay_facturas = True
        tarjetas.append(t)

    ctx = {
        "tarjetas": tarjetas,
        "filtro": filtro,
        "pendientes": CfdiEntrante.objects.filter(estado=ESTADO_PENDIENTE).count(),
        "puede_egresos": puede_resolver_egresos(request.user),
        "puede_facturas": puede_ligar_facturas(request.user),
        "volver": _url_lista(filtro),
    }
    if hay_facturas:
        ctx["facturas_libres"] = svc.facturas_sin_comprobante()
    if ctx["puede_egresos"]:
        from apps.el_catalogo.models import Proveedor

        ctx["proveedores"] = list(Proveedor.objects.filter(activo=True)
                                  .order_by("razon_social").only("pk", "razon_social", "rfc"))
    return render(request, "tesoreria/cfdi_recibidos.html", ctx)


@login_required
@requiere_permiso("tesoreria", "ver")
@require_POST
def cfdi_accion(request, pk):
    """Una decisión sobre un comprobante. Cada acción pide SU permiso."""
    from apps.el_catalogo.models import Proveedor
    from apps.facturacion import cfdi_recibidos as svc
    from apps.facturacion.models import CfdiEntrante, Factura
    from apps.tesoreria.models import Egreso

    c = get_object_or_404(CfdiEntrante, pk=pk)
    accion = (request.POST.get("accion") or "").strip()
    volver = request.POST.get("volver") or ""
    destino = volver if volver.startswith("/") and not volver.startswith("//") else _url_lista()

    permiso = {
        "ligar_factura": puede_ligar_facturas,
        "ligar_egreso": puede_resolver_egresos,
        "proveedor": puede_resolver_egresos,
        # El de ignorar depende de DE QUIÉN es el comprobante (ver `puede_ignorar`).
        "ignorar": lambda u: puede_ignorar(u, svc.clasificar(c)),
    }.get(accion)
    if permiso is None:
        messages.error(request, "No entendí qué hacer con ese comprobante.")
        return redirect(destino)
    if not permiso(request.user):
        return HttpResponseForbidden("Sin permisos para esta acción.")

    try:
        if accion == "ligar_factura":
            fac = Factura.objects.filter(pk=request.POST.get("factura")).first()
            if fac is None:
                messages.error(request, "Elige la factura a la que pertenece.")
                return redirect(destino)
            svc.ligar_factura(c, fac, request.user)
            messages.success(request, f"Comprobante ligado a {fac.codigo}.")
        elif accion == "ligar_egreso":
            eg = Egreso.vigentes.filter(pk=request.POST.get("egreso")).first()
            if eg is None:
                messages.error(request, "Ese egreso ya no está disponible.")
                return redirect(destino)
            svc.ligar_egreso(c, eg, request.user)
            messages.success(request, f"Comprobante ligado al egreso {eg.codigo}.")
        elif accion == "proveedor":
            prov = Proveedor.objects.filter(pk=request.POST.get("proveedor"), activo=True).first()
            if prov is None:
                messages.error(request, "Elige el proveedor.")
                return redirect(destino)
            svc.asignar_proveedor(c, prov, request.user)
            messages.success(request, f"Comprobante asignado a {prov.razon_social}.")
        elif accion == "ignorar":
            svc.ignorar(c, request.user, request.POST.get("motivo") or "")
            messages.success(request, "Comprobante marcado como ignorado.")
    except svc.CfdiNoResoluble as exc:
        messages.error(request, str(exc))
    return redirect(destino)


@login_required
@requiere_permiso("tesoreria", "ver")
def cfdi_archivo(request, pk):
    """Sirve el XML (o el PDF) del comprobante desde El Almacén."""
    from apps.facturacion.models import CfdiEntrante

    from lib import almacen

    c = get_object_or_404(CfdiEntrante, pk=pk)
    cual = request.GET.get("cual") or "xml"
    clave = c.pdf_id if cual == "pdf" else c.archivo_id
    if not clave:
        raise Http404("Ese comprobante no tiene ese archivo guardado.")
    try:
        contenido, mime, nombre = almacen.leer(clave)
    except Exception:  # noqa: BLE001
        raise Http404("No se pudo obtener el archivo.") from None
    if cual == "pdf":
        mime, disposicion = "application/pdf", "inline"
    else:
        # El XML llega de un buzón al que cualquiera escribe: se descarga, no
        # se interpreta en el navegador (un XML con hoja de estilos es HTML).
        mime, disposicion = "application/xml", "attachment"
    resp = HttpResponse(contenido, content_type=mime)
    resp["Content-Disposition"] = (
        f"{disposicion}; filename*=UTF-8''{quote(nombre or f'{c.uuid}.{cual}')}")
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


__all__ = ["cfdi_accion", "cfdi_archivo", "cfdi_recibidos",
           "puede_ignorar", "puede_ligar_facturas", "puede_resolver_egresos"]
