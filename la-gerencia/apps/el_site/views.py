"""El Site — vistas. Acceso restringido a super_admin + dueno.

3 cuadrantes:
- Infraestructura: host + containers + droplet + postgres + redis + caddy.
- Integraciones externas: tabla con cada plataforma + botón Probar ahora.
- Servicios internos: último evento Portavoz, DLQ, backup local, backup remoto, deploy.

Endpoints HTMX:
- /site/partial/infra            — auto-refresh cada 30s
- /site/partial/integraciones    — manual o tras probar
- /site/partial/internos         — auto-refresh cada 60s

POST /site/probar/<plataforma>   — fuerza un re-check de una plataforma
POST /site/probar-todas          — corre la batería completa
"""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.site import almacen, caddy, contenedores, droplet, host, internos, postgres, redis_status
from lib.site.registry import PLATAFORMAS, chequear


def _gate(request):
    if not request.user.is_authenticated:
        return redirect("/sign-in")
    if getattr(request.user, "rol", None) not in ("super_admin", "dueno"):
        return HttpResponseForbidden("Acceso restringido a super_admin y dueño.")
    return None


def _ctx_infra() -> dict:
    return {
        "host": host.snapshot(),
        "containers": contenedores.snapshot(),
        "droplet_local": droplet.info_local(),
        "droplet_remoto": droplet.info_remota(),
        "postgres": postgres.detalles(),
        "redis": redis_status.detalles(),
        "caddy": caddy.snapshot(),
    }


def _ctx_integraciones() -> dict:
    ultimo = almacen.ultimo_por_plataforma()
    filas = [
        {
            "plataforma": plat,
            "estado": ultimo.get(plat, {}).get("estado", "sin_datos"),
            "latencia_ms": ultimo.get(plat, {}).get("latencia_ms"),
            "mensaje_error": ultimo.get(plat, {}).get("mensaje_error"),
            "origen": ultimo.get(plat, {}).get("origen"),
            "probado_en": ultimo.get(plat, {}).get("probado_en"),
        }
        for plat in PLATAFORMAS
    ]
    return {"filas": filas}


def _ctx_internos() -> dict:
    return internos.snapshot()


def tablero(request):
    if (r := _gate(request)) is not None:
        return r
    ctx = {
        "infra": _ctx_infra(),
        "integraciones": _ctx_integraciones(),
        "internos": _ctx_internos(),
    }
    return render(request, "site/tablero.html", ctx)


def partial_infra(request):
    if (r := _gate(request)) is not None:
        return r
    return render(request, "site/partials/infra.html", {"infra": _ctx_infra()})


def partial_integraciones(request):
    if (r := _gate(request)) is not None:
        return r
    return render(request, "site/partials/integraciones.html", {"integraciones": _ctx_integraciones()})


def partial_internos(request):
    if (r := _gate(request)) is not None:
        return r
    return render(request, "site/partials/internos.html", {"internos": _ctx_internos()})


@require_http_methods(["POST"])
def probar_plataforma(request, plataforma: str):
    if (r := _gate(request)) is not None:
        return r
    if plataforma not in PLATAFORMAS:
        messages.error(request, f"Plataforma desconocida: {plataforma}")
        return redirect("site-tablero")
    res = chequear(plataforma)
    almacen.guardar(
        plataforma=plataforma,
        estado=res.get("estado", "error"),
        latencia_ms=res.get("latencia_ms"),
        mensaje_error=res.get("mensaje_error"),
        origen="manual",
        actor_email=request.user.email,
    )
    if res.get("estado") == "error":
        emitir(EventoPortavoz(
            tipo="site.integracion_fallo",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={
                "plataforma": plataforma,
                "estado": "error",
                "mensaje_error": (res.get("mensaje_error") or "")[:500],
                "latencia_ms": res.get("latencia_ms"),
                "origen": "manual",
                "actor_email": request.user.email,
            },
        ))
        messages.error(request, f"{plataforma}: {res.get('mensaje_error') or 'error'}")
    elif res.get("estado") == "no_configurada":
        messages.info(request, f"{plataforma}: no configurada.")
    else:
        messages.success(request, f"{plataforma}: OK ({res.get('latencia_ms')}ms).")
    if request.headers.get("HX-Request"):
        return render(request, "site/partials/integraciones.html", {"integraciones": _ctx_integraciones()})
    return redirect("site-tablero")


@require_http_methods(["POST"])
def probar_todas(request):
    if (r := _gate(request)) is not None:
        return r
    fallidas: list[str] = []
    for plat in PLATAFORMAS:
        res = chequear(plat)
        almacen.guardar(
            plataforma=plat,
            estado=res.get("estado", "error"),
            latencia_ms=res.get("latencia_ms"),
            mensaje_error=res.get("mensaje_error"),
            origen="manual",
            actor_email=request.user.email,
        )
        if res.get("estado") == "error":
            fallidas.append(plat)
            emitir(EventoPortavoz(
                tipo="site.integracion_fallo",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={
                    "plataforma": plat,
                    "estado": "error",
                    "mensaje_error": (res.get("mensaje_error") or "")[:500],
                    "latencia_ms": res.get("latencia_ms"),
                    "origen": "manual",
                    "actor_email": request.user.email,
                },
            ))
    if fallidas:
        messages.error(request, f"Plataformas en error: {', '.join(fallidas)}.")
    else:
        messages.success(request, f"Las {len(PLATAFORMAS)} plataformas respondieron sin errores.")
    if request.headers.get("HX-Request"):
        return render(request, "site/partials/integraciones.html", {"integraciones": _ctx_integraciones()})
    return redirect("site-tablero")
