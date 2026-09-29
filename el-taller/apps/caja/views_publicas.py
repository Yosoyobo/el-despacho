"""La página pública de pago: `/pagar/<token>/`, SIN sesión.

Es lo único de El Taller que ve un cliente, así que:

  · no pide login (ni lo ofrece): el token firmado es la llave, y es
    imposible de adivinar; un token falso o alterado es 404 sin tocar la base;
  · no se indexa (`noindex` en cabecera y en `<meta>`) ni filtra el token a
    terceros (`Referrer-Policy: no-referrer`) ni se guarda en caché;
  · tiene su propio límite de peticiones por IP (sin Redis, no se bloquea:
    cobrar pesa más que el límite);
  · sin llaves en Los Ajustes, la página NO existe: 404 (regla «apagado sin
    llaves»);
  · usa su propio layout (`caja/publica/base.html`): aunque la abra alguien del
    despacho con su sesión, se ve igual que la ve el cliente — sin menú.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lib import pasarelas
from lib.auditoria_acceso import ip_de
from lib.errors import RateLimitExcedido

from . import services
from .models import LinkPago
from .models.link_pago import token_de_url

logger = logging.getLogger("despacho.caja")

LIMITE_PETICIONES = 60
VENTANA_SEG = 300
# A dónde se deja salir al cliente: sólo a las pasarelas. Un `url` raro en la
# respuesta de la pasarela no se convierte en una redirección abierta.
DOMINIOS_PASARELA = ("stripe.com", "mercadopago.com", "mercadopago.com.mx", "mercadolibre.com")


def _cabeceras(resp):
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Referrer-Policy"] = "no-referrer"
    resp["Cache-Control"] = "no-store"
    return resp


def _pagina(request, plantilla: str, ctx: dict, status: int = 200):
    return _cabeceras(render(request, plantilla, ctx, status=status))


def _limite_excedido(request) -> bool:
    from lib.ratelimit import intentar
    try:
        intentar("caja_publica", ip_de(request) or "?", limite=LIMITE_PETICIONES, ventana_seg=VENTANA_SEG)
    except RateLimitExcedido:
        return True
    except Exception:  # noqa: BLE001 — sin Redis la página sigue sirviendo
        logger.warning("caja: sin límite de peticiones (Redis no respondió)")
    return False


def _link(firmado: str) -> LinkPago:
    if not services.configurada():
        raise Http404("La Caja está apagada.")
    token = token_de_url(firmado)
    if not token:
        raise Http404("Link inexistente.")
    link = (LinkPago.objects.select_related("cliente", "factura", "cotizacion")
            .filter(token=token).first())
    if link is None:
        raise Http404("Link inexistente.")
    return services.marcar_vencido_si_toca(link)


def _contexto(link: LinkPago, **extra) -> dict:
    estado = pasarelas.estado()
    opciones = [
        {"clave": p, "nombre": estado[p]["nombre"], "prueba": estado[p]["prueba"],
         "url": link.ruta_publica(p)}
        for p in estado["pasarelas"]
    ]
    return {
        "link": link,
        "opciones": opciones,
        "modo_prueba": estado["prueba"],
        "cliente_nombre": getattr(link.cliente, "razon_social", "") if link.cliente_id else "",
        **extra,
    }


def _limitado(request):
    return _pagina(request, "caja/publica/limite.html", {}, status=429)


@require_GET
def pagar(request, firmado):
    if _limite_excedido(request):
        return _limitado(request)
    link = _link(firmado)
    return _pagina(request, "caja/publica/pagar.html", _contexto(link))


def _salida_segura(url: str) -> bool:
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    host = (partes.hostname or "").lower()
    return partes.scheme == "https" and any(host == d or host.endswith("." + d) for d in DOMINIOS_PASARELA)


@require_POST
def pagar_con(request, firmado, pasarela):
    if _limite_excedido(request):
        return _limitado(request)
    link = _link(firmado)
    try:
        destino = services.abrir_cobro(link, pasarela)
    except ValueError as exc:
        return _pagina(request, "caja/publica/pagar.html", _contexto(link, error=str(exc)), status=400)
    except pasarelas.ErrorPasarela as exc:
        logger.warning("caja: no se pudo abrir el cobro del link %s en %s: %s", link.pk, pasarela, exc)
        return _pagina(request, "caja/publica/pagar.html", _contexto(
            link, error="La forma de pago no respondió. Intenta de nuevo en unos minutos o elige otra."),
            status=502)
    if not _salida_segura(destino):
        logger.error("caja: la pasarela devolvió una URL fuera de su dominio: %s", destino[:120])
        return _pagina(request, "caja/publica/pagar.html",
                       _contexto(link, error="No se pudo abrir la forma de pago."), status=502)
    return _cabeceras(HttpResponseRedirect(destino, status=303))


@require_GET
def gracias(request, firmado):
    if _limite_excedido(request):
        return _limitado(request)
    link = _link(firmado)
    return _pagina(request, "caja/publica/gracias.html", _contexto(link))


@require_GET
def cancelado(request, firmado):
    if _limite_excedido(request):
        return _limitado(request)
    link = _link(firmado)
    return _pagina(request, "caja/publica/cancelado.html", _contexto(link))
