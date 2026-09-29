"""Las pantallas de La Recepción.

Toda vista que muestra algo del cliente toma el cliente de `request.cliente`
(lo pone `SesionClienteMiddleware`, que también cierra la puerta a quien no
tiene sesión) y pide sus datos a `consultas`, que filtra por él. Nunca se busca
un objeto por su id a secas.

Sin mensajes ni chat (decisión de Oscar: «NO chat de cliente»). Sin El Chalán.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from lib.errors import RateLimitExcedido
from lib.ratelimit import intentar
from portal import servicios

from . import consultas

logger = logging.getLogger(__name__)

#: Rate-limit (regla §4 #5: 5 intentos / 15 min). Por correo Y por dirección:
#: el primero frena a quien le llena la bandeja a alguien, el segundo a quien
#: prueba correos para ver cuál es cliente.
LIMITE_POR_CORREO = 5
LIMITE_POR_IP = 20
VENTANA_SEG = 15 * 60


def _ip(request) -> str:
    from lib.auditoria_acceso import ip_de

    return ip_de(request) or "?"


def _limitar(scope: str, identidad: str, limite: int) -> bool:
    """True si todavía hay cupo. Si Redis no contesta, se niega (cerrado por
    default, igual que el login del equipo): mejor «intenta en un rato» que un
    portal sin freno."""
    try:
        intentar(scope, identidad, limite=limite, ventana_seg=VENTANA_SEG)
        return True
    except RateLimitExcedido:
        return False
    except Exception:  # noqa: BLE001 — Redis caído
        logger.warning("portal: rate-limit sin Redis (%s)", scope, exc_info=True)
        return False


def _siguiente(request, valor: str) -> str:
    if valor and valor.startswith("/") and url_has_allowed_host_and_scheme(
            valor, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return valor
    return "/"


# ── Públicas: entrar, salir, legales ────────────────────────────────────────


@require_http_methods(["GET", "POST"])
def entrar(request):
    """Pide el correo. La respuesta es LA MISMA exista o no el acceso."""
    if request.acceso is not None:
        return redirect("/")
    siguiente = _siguiente(request, request.GET.get("next") or request.POST.get("next") or "")
    ctx = {"siguiente": siguiente, "email": (request.GET.get("email") or "")[:254],
           "google": _google_disponible()}
    if request.method == "GET":
        return render(request, "portal_cliente/entrar.html", ctx)

    email = servicios.normalizar_email(request.POST.get("email", ""))[:254]
    ctx["email"] = email
    if not email or "@" not in email:
        ctx["error"] = "Escribe tu correo."
        return render(request, "portal_cliente/entrar.html", ctx, status=400)
    if not (_limitar("portal_enlace_ip", _ip(request), LIMITE_POR_IP)
            and _limitar("portal_enlace_correo", email, LIMITE_POR_CORREO)):
        ctx["error"] = "Demasiados intentos. Espera unos minutos y vuelve a pedir tu enlace."
        return render(request, "portal_cliente/entrar.html", ctx, status=429)
    try:
        servicios.pedir_enlace(email, request)
    except Exception:  # noqa: BLE001 — ni un error delata si el correo existe
        logger.exception("portal: falló pedir_enlace")
    return render(request, "portal_cliente/enlace_enviado.html", {"email": email})


_MOTIVO_TEXTO = {
    servicios.CANJE_INVALIDO: "Este enlace no es válido. Revisa que lo hayas abierto completo desde tu correo.",
    servicios.CANJE_USADO: "Este enlace ya se usó. Cada enlace sirve una sola vez: pide uno nuevo.",
    servicios.CANJE_EXPIRADO: "Este enlace ya venció. Pide uno nuevo: llega en un momento.",
    servicios.CANJE_SIN_ACCESO: "Este acceso ya no está activo. Si crees que es un error, avísale a tu contacto en Learning Center.",
}


@require_http_methods(["GET", "POST"])
def canjear(request, token: str):
    """GET muestra el botón «Entrar»; el POST gasta el enlace (ver `portal.servicios`:
    los filtros de correo abren los enlaces antes que la persona)."""
    if request.method == "GET":
        enlace, motivo = servicios.buscar_enlace(token)
        if motivo:
            email = enlace.acceso.email if (enlace is not None and motivo != servicios.CANJE_SIN_ACCESO) else ""
            return render(request, "portal_cliente/enlace_invalido.html",
                          {"mensaje": _MOTIVO_TEXTO[motivo], "email": email}, status=410
                          if motivo in (servicios.CANJE_USADO, servicios.CANJE_EXPIRADO) else 404)
        return render(request, "portal_cliente/canjear.html", {
            "nombre": enlace.acceso.nombre_visible,
            "empresa": enlace.acceso.cliente.razon_social,
        })

    if not _limitar("portal_canje_ip", _ip(request), LIMITE_POR_IP):
        return render(request, "portal_cliente/enlace_invalido.html",
                      {"mensaje": "Demasiados intentos. Espera unos minutos."}, status=429)
    acceso, motivo = servicios.canjear(token, request)
    if acceso is None:
        return render(request, "portal_cliente/enlace_invalido.html",
                      {"mensaje": _MOTIVO_TEXTO.get(motivo, _MOTIVO_TEXTO[servicios.CANJE_INVALIDO])},
                      status=410)
    servicios.abrir_sesion(request, acceso)
    return redirect("/")


@require_POST
def salir(request):
    if request.acceso is not None:
        servicios.registrar_evento(request.acceso, "salida", "", request)
    servicios.cerrar_sesion(request)
    return redirect("/entrar/")


@require_safe
def privacidad(request):
    return render(request, "portal_cliente/legal/privacidad.html")


@require_safe
def terminos(request):
    return render(request, "portal_cliente/legal/terminos.html")


@require_safe
def ping(request):
    return HttpResponse("ok", content_type="text/plain")


# ── Google (opcional, §4 #7: sólo si el correo YA tiene acceso) ─────────────

SESION_STATE = "_portal_google_state"
SESION_NEXT = "_portal_google_next"


def _google_disponible() -> bool:
    """«Entrar con Google» sólo si La Gerencia lo prendió (Los Ajustes → Portal
    de clientes; decisión de Oscar: apagado por default, sólo el enlace por
    correo) Y el SSO tiene sus credenciales. Apagado, ni el botón ni las rutas."""
    try:
        from lib.google_oauth import GoogleOAuthConfig
        from portal.models import ConfiguracionPortal

        return ConfiguracionPortal.obtener().google_activo and GoogleOAuthConfig.esta_configurado()
    except Exception:  # noqa: BLE001
        return False


@require_safe
def google_iniciar(request):
    if not _google_disponible():
        return redirect("/entrar/")
    from lib.google_oauth import (
        construir_url_autorizacion,
        generar_state_nonce,
        redirect_uri_desde_request,
    )

    state, nonce = generar_state_nonce()
    request.session[SESION_STATE] = state
    request.session[SESION_NEXT] = _siguiente(request, request.GET.get("next", ""))
    return redirect(construir_url_autorizacion(redirect_uri_desde_request(request), state=state, nonce=nonce))


@require_safe
def google_callback(request):
    from lib.google_oauth import (
        GoogleOAuthError,
        intercambiar_codigo_por_perfil,
        redirect_uri_desde_request,
    )

    if not _google_disponible():
        return redirect("/entrar/")
    esperado = request.session.pop(SESION_STATE, None)
    siguiente = request.session.pop(SESION_NEXT, "/") or "/"
    code, state = request.GET.get("code", ""), request.GET.get("state", "")
    if request.GET.get("error") or not code or not state or state != esperado:
        return _error_google(request, "No se pudo completar la entrada con Google. Vuelve a intentarlo.")
    try:
        perfil = intercambiar_codigo_por_perfil(code, redirect_uri_desde_request(request))
    except GoogleOAuthError:
        return _error_google(request, "Google no confirmó tu cuenta. Vuelve a intentarlo o entra con tu correo.")
    acceso = servicios.acceso_activo_por_email(perfil.email) if perfil.email_verified else None
    if acceso is None:
        # Nunca se crea un acceso aquí (§4 #7): lo da el despacho, no Google.
        return _error_google(
            request,
            f"La cuenta de Google {perfil.email} no tiene acceso al portal. Entra con el "
            "correo al que te llegó la invitación, o pídele a tu contacto en Learning "
            "Center que te invite.", status=403)
    servicios.marcar_entrada(acceso, request, via="google")
    servicios.abrir_sesion(request, acceso)
    return redirect(_siguiente(request, siguiente))


def _error_google(request, mensaje: str, status: int = 400):
    return render(request, "portal_cliente/enlace_invalido.html",
                  {"mensaje": mensaje, "titulo": "No pudimos entrar con Google"}, status=status)


# ── Con sesión: lo del cliente ───────────────────────────────────────────────


@require_safe
def inicio(request):
    return render(request, "portal_cliente/inicio.html", {
        "resumen": consultas.resumen(request.cliente), "seccion": "inicio",
        "pasos_ciclo": consultas.PASOS,
    })


@require_safe
def proyectos(request):
    lista = consultas.proyectos_de(request.cliente)
    return render(request, "portal_cliente/proyectos.html", {
        "activos": [p for p in lista if not p.terminado],
        "terminados": [p for p in lista if p.terminado],
        "pasos": consultas.PASOS, "seccion": "proyectos",
    })


@require_safe
def proyecto(request, codigo: str):
    p = consultas.proyecto_de(request.cliente, codigo)
    if p is None:
        raise Http404
    return render(request, "portal_cliente/proyecto.html",
                  {"p": p, "pasos": consultas.PASOS, "seccion": "proyectos"})


@require_safe
def cotizaciones(request):
    lista = consultas.cotizaciones_de(request.cliente)
    return render(request, "portal_cliente/cotizaciones.html", {
        "por_responder": [c for c in lista if c.por_responder],
        "respondidas": [c for c in lista if not c.por_responder],
        "seccion": "cotizaciones",
    })


def _url_pago_anticipo(c) -> str | None:
    if c.fase != "ganada" or not c.anticipo or c.anticipo <= 0:
        return None
    return consultas.url_pago(c.obj)


@require_safe
def cotizacion(request, pk: int):
    c = consultas.cotizacion_cliente(request.cliente, pk)
    if c is None:
        raise Http404
    return render(request, "portal_cliente/cotizacion.html", {
        "c": c, "url_pago": _url_pago_anticipo(c), "seccion": "cotizaciones",
        "nombre_sugerido": request.acceso.nombre,
    })


def _responder(request, pk: int, aprobar: bool):
    from apps.cotizaciones import services as cot_services

    cot = consultas.cotizacion_de(request.cliente, pk)
    if cot is None:
        raise Http404
    c = consultas.cotizacion_cliente(request.cliente, pk)
    nombre = (request.POST.get("nombre") or "").strip()[:200]
    destino = f"/cotizaciones/{cot.pk}/"
    if not nombre:
        messages.error(request, "Escribe tu nombre: queda registrado junto con tu respuesta.")
        return redirect(destino)
    acceso = request.acceso
    cuando = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    ip = _ip(request)
    try:
        if aprobar:
            if not c.se_puede_aprobar:
                messages.error(request, "Esta cotización ya no se puede aprobar desde aquí. "
                               "Escríbele a tu contacto en Learning Center.")
                return redirect(destino)
            if request.POST.get("acepto") != "1":
                messages.error(request, "Marca la casilla para confirmar que apruebas la cotización.")
                return redirect(destino)
            cot_services.marcar_aprobada(
                cot, None, nombre=nombre, email=acceso.email,
                referencia=f"Portal de clientes · {acceso.email} · {cuando} · IP {ip}"[:200],
            )
            tipo_evento, tipo_bitacora = "portal.cotizacion_aprobada", "aprobacion"
            messages.success(request, "¡Listo! Aprobaste la cotización. El equipo ya está enterado.")
        else:
            if not c.se_puede_rechazar:
                messages.error(request, "Esta cotización ya tiene respuesta.")
                return redirect(destino)
            motivo = (request.POST.get("motivo") or "").strip()[:1000]
            if not motivo:
                messages.error(request, "Cuéntanos brevemente por qué la rechazas: nos ayuda a ajustarla.")
                return redirect(destino)
            cot_services.marcar_rechazada(
                cot, None,
                motivo=(f"{motivo}\n\n— {nombre} ({acceso.email}) desde el portal de clientes, "
                        f"{cuando}, IP {ip}"),
            )
            tipo_evento, tipo_bitacora = "portal.cotizacion_rechazada", "rechazo"
            messages.success(request, "Registramos tu respuesta. Gracias por avisarnos.")
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(destino)

    servicios.registrar_evento(acceso, tipo_bitacora, f"{cot.codigo} · {nombre}", request)
    from portal import avisos

    avisos.cotizacion_respondida(cot, acceso, nombre=nombre, aprobada=aprobar, tipo_evento=tipo_evento)
    return redirect(destino)


@require_POST
def cotizacion_aprobar(request, pk: int):
    return _responder(request, pk, aprobar=True)


@require_POST
def cotizacion_rechazar(request, pk: int):
    return _responder(request, pk, aprobar=False)


@require_safe
def facturas(request):
    lista = consultas.facturas_de(request.cliente)
    return render(request, "portal_cliente/facturas.html", {
        "con_saldo": [f for f in lista if f.saldo > 0],
        "pagadas": [f for f in lista if f.saldo <= 0],
        "seccion": "facturas",
    })


@require_safe
def factura(request, pk: int):
    f = consultas.factura_cliente(request.cliente, pk)
    if f is None:
        raise Http404
    return render(request, "portal_cliente/factura.html", {
        "f": f, "pagos": consultas.pagos_de_factura(f.obj),
        "url_pago": consultas.url_pago(f.obj) if f.saldo > 0 else None,
        "seccion": "facturas",
    })


# ── Descargas: el documento ya generado, desde Drive, SÓLO del propio cliente ─


def _descargar(request, file_id: str, nombre: str, detalle: str):
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET"])
    if not file_id:
        raise Http404
    try:
        from lib.google_drive import drive

        contenido, mime, _ = drive.descargar(file_id)
    except Exception:  # noqa: BLE001 — Drive caído o sin conectar
        logger.warning("portal: no se pudo bajar %s de Drive", file_id, exc_info=True)
        messages.error(request, "No pudimos traer el documento en este momento. Intenta en unos minutos.")
        return redirect(request.META.get("HTTP_REFERER") or "/")
    servicios.registrar_evento(request.acceso, "descarga", detalle, request)
    nombre_ascii = nombre.encode("ascii", "ignore").decode() or "documento"
    resp = HttpResponse(contenido, content_type=mime or "application/octet-stream")
    resp["Content-Disposition"] = (f'attachment; filename="{nombre_ascii}"; '
                                   f"filename*=UTF-8''{quote(nombre)}")
    resp["Cache-Control"] = "private, no-store"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


def cotizacion_pdf(request, pk: int):
    cot = consultas.cotizacion_de(request.cliente, pk)
    if cot is None:
        raise Http404
    return _descargar(request, cot.pdf_file_id, f"{cot.nombre_pdf}.pdf", f"PDF {cot.codigo}")


def factura_pdf(request, pk: int):
    f = consultas.factura_de(request.cliente, pk)
    if f is None:
        raise Http404
    return _descargar(request, f.pdf_file_id, f"Factura-{f.folio or f.codigo}.pdf", f"PDF {f.codigo}")


def factura_xml(request, pk: int):
    f = consultas.factura_de(request.cliente, pk)
    if f is None:
        raise Http404
    return _descargar(request, f.xml_file_id, f"Factura-{f.folio or f.codigo}.xml", f"XML {f.codigo}")


def no_encontrado(request, exception=None):
    return render(request, "portal_cliente/404.html", status=404)
