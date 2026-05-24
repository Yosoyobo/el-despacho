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
from lib.site import (
    almacen,
    caddy,
    contenedores,
    droplet,
    historial,
    host,
    internos,
    postgres,
    redis_status,
)
from lib.site.registry import PLATAFORMAS, chequear


# `_gauge` migrado a `lib/site/gauges.gauge` para que el Taller pueda
# reusarlo. El alias `_gauge` se conserva para compat hacia abajo en
# este archivo.
from lib.site.gauges import gauge as _gauge  # noqa: E402


def _barra(pct: float | None, *, umbral_warn: float = 60, umbral_err: float = 80) -> dict:
    if pct is None:
        return {"disponible": False}
    p = max(0.0, min(100.0, float(pct)))
    color = "error" if p >= umbral_err else "warning" if p >= umbral_warn else "success"
    return {"disponible": True, "pct": round(p, 1), "color": color}


def _gate(request):
    if not request.user.is_authenticated:
        return redirect("/sign-in")
    if getattr(request.user, "rol", None) not in ("super_admin", "dueno"):
        return HttpResponseForbidden("Acceso restringido a super_admin y dueño.")
    return None


def _ctx_infra() -> dict:
    h = host.snapshot()
    c = contenedores.snapshot()
    cd = caddy.snapshot()

    # Pre-cálculo de gauges/barras para SVG inline (sin libs).
    mem_pct = h["memoria"].get("pct_usado") if h["memoria"].get("disponible") else None
    dis_pct = h["disco"].get("pct_usado") if h["disco"].get("disponible") else None
    cpu = h["cpu_load"]
    load_pct = None
    if cpu.get("disponible") and cpu.get("cores"):
        load_pct = (cpu["load_1"] / max(cpu["cores"], 1)) * 100

    # Containers donut
    info_c = c.get("info", {}) if isinstance(c, dict) else {}
    running = info_c.get("running", 0) if info_c.get("disponible") else 0
    stopped = info_c.get("stopped", 0) if info_c.get("disponible") else 0
    total_c = max(running + stopped, 1)
    pct_running = (running / total_c) * 100 if info_c.get("disponible") else None

    # Cert más cercano
    certs = cd.get("certs") or [] if cd.get("disponible") else []
    cert_min = None
    if certs:
        cert_min = min((x.get("dias_para_expirar") or 9999) for x in certs)

    return {
        "host": h,
        "containers": c,
        "droplet_local": droplet.info_local(),
        "droplet_remoto": droplet.info_remota(),
        "postgres": postgres.detalles(),
        "redis": redis_status.detalles(),
        "caddy": cd,
        "gauges": {
            "cpu": _gauge(load_pct, umbral_warn=70, umbral_err=100),
            "memoria": _gauge(mem_pct),
            "disco": _gauge(dis_pct, umbral_warn=75, umbral_err=85),
            "containers_running": _gauge(pct_running, umbral_warn=0, umbral_err=0)
            if info_c.get("disponible") else {"disponible": False},
        },
        "containers_resumen": {
            "running": running,
            "stopped": stopped,
            "total": running + stopped,
            "pct_running": round(pct_running, 1) if pct_running is not None else None,
        },
        "cert_min_dias": cert_min,
    }


def _ctx_integraciones() -> dict:
    import json as _json

    ultimo = almacen.ultimo_por_plataforma()
    filas = []
    for plat in PLATAFORMAS:
        u = ultimo.get(plat, {})
        serie = historial.serie_latencia(plat, n=20)
        filas.append({
            "plataforma": plat,
            "estado": u.get("estado", "sin_datos"),
            "latencia_ms": u.get("latencia_ms"),
            "mensaje_error": u.get("mensaje_error"),
            "origen": u.get("origen"),
            "probado_en": u.get("probado_en"),
            "spark_json": _json.dumps(serie),
            "historial_n": len(serie),
        })

    resumen = historial.resumen_estados()
    # Dona ApexCharts — arma una lista de segmentos no vacíos.
    segmentos = []
    if resumen.get("ok"):
        segmentos.append({"label": "OK", "valor": resumen["ok"], "color": "#12b76a"})
    if resumen.get("error"):
        segmentos.append({"label": "Error", "valor": resumen["error"], "color": "#f04438"})
    if resumen.get("no_configurada"):
        segmentos.append({"label": "No configurada", "valor": resumen["no_configurada"], "color": "#98a2b3"})
    if resumen.get("sin_datos"):
        segmentos.append({"label": "Sin datos", "valor": resumen["sin_datos"], "color": "#d0d5dd"})

    return {
        "filas": filas,
        "resumen": resumen,
        "total": sum(resumen.values()),
        "dona_json": _json.dumps(segmentos),
        "area_latencias_json": _json.dumps(historial.series_apex_por_plataforma(n=60)),
        "barras_chequeos_json": _json.dumps(historial.histograma_chequeos(dias=14)),
    }


def _ctx_internos() -> dict:
    return internos.snapshot()


def _ctx_global(infra: dict, integ: dict, intern: dict) -> dict:
    """KPIs grandes del header del tablero."""
    return {
        "kpi_ok": integ["resumen"].get("ok", 0),
        "kpi_error": integ["resumen"].get("error", 0),
        "kpi_running": infra["containers_resumen"]["running"],
        "kpi_total_containers": infra["containers_resumen"]["total"],
        "kpi_cert_min": infra["cert_min_dias"],
        "kpi_dlq": intern.get("portavoz_dlq", 0),
    }


def tablero(request):
    if (r := _gate(request)) is not None:
        return r
    infra = _ctx_infra()
    integ = _ctx_integraciones()
    intern = _ctx_internos()
    try:
        from lib.analistas.stats import resumen_global, tarjetas_chalanes
        chalanes_resumen = resumen_global(dias=30)
        chalanes_tarjetas = tarjetas_chalanes(dias=30)
    except Exception:  # noqa: BLE001 — El Site nunca debe tumbarse por esto.
        chalanes_resumen = {"costo_total": 0, "llamadas_total": 0, "tokens_total": 0, "por_proveedor": []}
        chalanes_tarjetas = []
    ctx = {
        "infra": infra,
        "integraciones": integ,
        "internos": intern,
        "global": _ctx_global(infra, integ, intern),
        "chalanes_resumen": chalanes_resumen,
        "chalanes_tarjetas": chalanes_tarjetas,
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
