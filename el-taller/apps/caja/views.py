"""La Caja en El Taller — la pantalla (en Tesorería) y los modales de los links.

Todo pasa por permiso granular (§4 #20): `caja.ver` para mirar,
`caja.crear_link` para generar y mandar, `caja.anular_link`, y
`caja.revisar_pago` para decidir lo que llegó y no cuadró. Además, para hacer el
link de una factura hay que poder ver la factura (y la cotización, para el
anticipo): La Caja no abre una puerta que el módulo dueño tiene cerrada.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from lib import pasarelas
from lib.permisos import (
    puede_anular_link_caja,
    puede_crear_link_caja,
    puede_revisar_pago_caja,
    puede_ver_cotizaciones,
    puede_ver_facturacion,
    requiere_permiso,
)

from . import services
from .models import LinkPago, PagoRecibido

FILTROS = (("vigente", "Vigentes"), ("pagado", "Pagados"), ("anulado", "Anulados"), ("vencido", "Vencidos"))
ESTADOS_FILTRO = {clave for clave, _ in FILTROS}


def _base() -> str:
    """La dirección pública del Taller (detrás de El Portero, la petición no la sabe)."""
    from django.conf import settings
    return getattr(settings, "TALLER_URL", "https://taller.learningcenter.mx/").rstrip("/")


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _ctx_link(request, link: LinkPago, **extra) -> dict:
    return {
        "link": link,
        "url_publica": link.url_publica(),
        "puede_anular": puede_anular_link_caja(request.user) and link.cobrable,
        "puede_mandar": puede_crear_link_caja(request.user) and link.cobrable,
        "correo_cliente": (getattr(link.cliente, "email_contacto", "") or "").strip() if link.cliente_id else "",
        "caja_estado": pasarelas.estado(),
        **extra,
    }


def _modal_link(request, link: LinkPago, status: int = 200, **extra):
    return render(request, "caja/_modal_link.html", _ctx_link(request, link, **extra), status=status)


def _apagada(request):
    msg = "La Caja está apagada: faltan las llaves de Stripe o MercadoPago en Los Ajustes."
    if _es_htmx(request):
        return render(request, "caja/_modal_mensaje.html", {"titulo": "La Caja", "mensaje": msg}, status=409)
    messages.error(request, msg)
    return redirect("caja:landing")


# ── Pantalla ─────────────────────────────────────────────────────────────────


@requiere_permiso("caja", "ver")
def landing(request):
    estado = (request.GET.get("estado") or "").strip()
    links = LinkPago.objects.select_related("cliente", "factura", "cotizacion", "proyecto", "creado_por")
    if estado in ESTADOS_FILTRO:
        links = links.filter(estado=estado)
    pagos = PagoRecibido.objects.select_related("link", "link__cliente", "ingreso", "revisado_por")
    estado_caja = pasarelas.estado()
    resumen = services.resumen()
    return render(request, "caja/landing.html", {
        "caja_estado": estado_caja,
        "pasarelas_activas": [estado_caja[p] for p in estado_caja["pasarelas"]],
        "filtros": FILTROS,
        "resumen": resumen,
        "subtexto_pagos": f"{resumen['pagos_mes']} pago{'' if resumen['pagos_mes'] == 1 else 's'}",
        "links": list(links[:60]),
        "estado_filtro": estado,
        "por_revisar": list(pagos.filter(estado="por_revisar")[:30]),
        "pagos": list(pagos.exclude(estado="por_revisar")[:40]),
        "puede_revisar": puede_revisar_pago_caja(request.user),
        "puede_anular": puede_anular_link_caja(request.user),
        "webhook_stripe": f"{_base()}{reverse('caja:webhook-stripe')}",
        "webhook_mp": f"{_base()}{reverse('caja:webhook-mercadopago')}",
    })


@requiere_permiso("caja", "ver")
def link_detalle(request, pk):
    link = get_object_or_404(
        LinkPago.objects.select_related("cliente", "factura", "cotizacion", "proyecto", "creado_por"), pk=pk)
    services.marcar_vencido_si_toca(link)
    return render(request, "caja/link_detalle.html", {
        **_ctx_link(request, link),
        "pagos": list(link.pagos.select_related("ingreso").all()),
    })


# ── Crear links ──────────────────────────────────────────────────────────────


def _link_de_objeto(request, objeto, url_modal: str):
    """GET: modal con el link vigente (si ya hay por el mismo monto) o con el
    botón para generarlo. POST: lo genera o reusa y enseña el enlace."""
    if not services.configurada():
        return _apagada(request)
    datos = services.que_cobrar(objeto)
    if datos is None:
        return render(request, "caja/_modal_mensaje.html", {
            "titulo": "Link de pago",
            "mensaje": "No hay nada que cobrar en línea aquí (sin saldo, sin emitir o sin anticipo pendiente).",
        })
    if request.method == "POST":
        link = services.link_para(objeto, actor=request.user)
        if link is None:  # carrera: se cobró mientras tanto
            return render(request, "caja/_modal_mensaje.html",
                          {"titulo": "Link de pago", "mensaje": "Ya no hay saldo que cobrar."})
        if not _es_htmx(request):
            return redirect("caja:link-detalle", pk=link.pk)
        return _modal_link(request, link)
    filtro = {"estado": "vigente", "tipo": datos["tipo"]}
    filtro["factura" if datos["tipo"] == "factura" else "cotizacion"] = (
        datos["factura"] if datos["tipo"] == "factura" else datos["cotizacion"])
    existente = next((lk for lk in LinkPago.objects.filter(**filtro) if lk.cobrable
                      and abs(lk.monto - datos["monto"]) < services.TOLERANCIA), None)
    if existente is not None:
        return _modal_link(request, existente)
    return render(request, "caja/_modal_generar.html", {
        "datos": datos, "url_post": url_modal, "caja_estado": pasarelas.estado(),
    })


@requiere_permiso("caja", "crear_link")
@require_http_methods(["GET", "POST"])
def link_factura(request, pk):
    from apps.facturacion.models import Factura

    if not puede_ver_facturacion(request.user):
        return HttpResponseForbidden("Sin acceso a Facturación.")
    fac = get_object_or_404(Factura.objects.select_related("cliente", "proyecto"), pk=pk)
    return _link_de_objeto(request, fac, reverse("caja:link-factura", args=[fac.pk]))


@requiere_permiso("caja", "crear_link")
@require_http_methods(["GET", "POST"])
def link_cotizacion(request, pk):
    from apps.cotizaciones.models import Cotizacion

    if not puede_ver_cotizaciones(request.user):
        return HttpResponseForbidden("Sin acceso a Cotizaciones.")
    cot = get_object_or_404(Cotizacion.objects.select_related("cliente", "proyecto"), pk=pk)
    return _link_de_objeto(request, cot, reverse("caja:link-cotizacion", args=[cot.pk]))


@requiere_permiso("caja", "crear_link")
@require_http_methods(["GET", "POST"])
def link_libre(request):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    if not services.configurada():
        return _apagada(request)
    fuente = request.POST if request.method == "POST" else request.GET
    proyecto = cliente = None
    if (pid := (fuente.get("proyecto") or "").strip()).isdigit():
        proyecto = get_object_or_404(Proyecto.objects.select_related("cliente"), pk=int(pid))
        cliente = proyecto.cliente
    elif (cid := (fuente.get("cliente") or "").strip()).isdigit():
        cliente = get_object_or_404(Cliente, pk=int(cid))
    if cliente is None:
        return render(request, "caja/_modal_mensaje.html", {
            "titulo": "Cobrar con link", "mensaje": "El link libre sale de la ficha de un cliente o de un proyecto."})
    ctx = {"cliente": cliente, "proyecto": proyecto, "caja_estado": pasarelas.estado(),
           "monto": fuente.get("monto", ""), "concepto": fuente.get("concepto", "")}
    if request.method == "POST":
        try:
            link = services.crear_link_libre(
                monto=(fuente.get("monto") or "").replace(",", "").replace("$", "").strip(),
                concepto=fuente.get("concepto") or "", actor=request.user,
                cliente=cliente, proyecto=proyecto)
        except ValueError as exc:
            return render(request, "caja/_modal_libre.html", {**ctx, "error": str(exc)}, status=400)
        if not _es_htmx(request):
            return redirect("caja:link-detalle", pk=link.pk)
        return _modal_link(request, link)
    return render(request, "caja/_modal_libre.html", ctx)


# ── Acciones sobre un link ───────────────────────────────────────────────────


@requiere_permiso("caja", "anular_link")
@require_POST
def link_anular(request, pk):
    link = get_object_or_404(LinkPago, pk=pk)
    try:
        services.anular(link, actor=request.user,
                        motivo=(request.POST.get("motivo") or "").strip() or "Anulado a mano.")
    except ValueError as exc:
        if _es_htmx(request):
            return _modal_link(request, link, status=400, error=str(exc))
        messages.error(request, str(exc))
        return redirect("caja:link-detalle", pk=link.pk)
    if _es_htmx(request):
        return _modal_link(request, link, aviso="Link anulado. Si el cliente lo abre, verá que ya no es válido.")
    messages.success(request, "Link anulado.")
    return redirect("caja:link-detalle", pk=link.pk)


@requiere_permiso("caja", "crear_link")
@require_POST
def link_correo(request, pk):
    link = get_object_or_404(LinkPago.objects.select_related("cliente"), pk=pk)
    res = services.enviar_por_correo(link, actor=request.user)
    texto = (f"Link enviado a {link.cliente.email_contacto}." if res.ok
             else f"No se mandó: {res.error or res.detalle}")
    if _es_htmx(request):
        return _modal_link(request, link, **({"aviso": texto} if res.ok else {"error": texto}))
    (messages.success if res.ok else messages.error)(request, texto)
    return redirect("caja:link-detalle", pk=link.pk)


# ── Pagos por revisar ────────────────────────────────────────────────────────


@requiere_permiso("caja", "revisar_pago")
@require_POST
def pago_revisar(request, pk):
    pago = get_object_or_404(PagoRecibido.objects.select_related("link"), pk=pk)
    accion = (request.POST.get("accion") or "").strip()
    try:
        services.revisar_pago(pago, accion=accion, actor=request.user, nota=request.POST.get("nota") or "")
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Pago registrado." if accion == "registrar" else "Pago descartado.")
    destino = reverse("caja:landing")
    if _es_htmx(request):
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(destino)
