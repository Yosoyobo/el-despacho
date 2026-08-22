"""El Vigía — la pantalla de pared del NUC, en vivo.

Se abre en el navegador DEL PROPIO NUC (Ubuntu Desktop) a pantalla completa, y
arranca sola tras un reinicio (ver `infra/vigia/`). Muestra tres cosas a la vez:
el fierro, las peticiones conforme llegan, y el trabajo que el sistema está
haciendo por el despacho.

── Por qué NO pide sesión ─────────────────────────────────────────────────────
Porque no puede. En producción `SESSION_COOKIE_SECURE = True`, así que la cookie
de sesión no viaja por `http://localhost:8201`, que es exactamente cómo la abre el
navegador del NUC. Una pantalla de kiosco que pidiera login además tendría que
loguearse sola tras cada reinicio, lo cual es peor.

Lo que la protege es **dónde se puede pedir**, y son dos candados a la vez:

1. El `Host` de la petición tiene que estar en la lista de locales (loopback, la
   IP del tailnet, la de la LAN). El dominio público NO está, así que
   `gerencia.learningcenter.mx/site/vivo/` devuelve 404 — ni siquiera revela que
   la ruta existe.
2. La petición NO puede traer `X-Forwarded-For`. El Portero siempre lo pone al
   proxear, así que su ausencia significa «esto llegó directo al contenedor, no
   desde internet». Es el candado que sobrevive a que alguien, algún día, agregue
   el dominio a la lista de arriba por error.

La página es de sólo lectura: no hay un solo POST en este archivo.
"""

from __future__ import annotations

import ipaddress
import os

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_safe

from lib.site import actividad, contenedores, internos
from lib.site.gauges import snapshot_gauges_minimo

# Hosts desde los que se puede pedir El Vigía. `VIGIA_HOSTS` permite sumar otra
# máquina del tailnet sin tocar código. El dominio público jamás va aquí.
_LOCALES = {"localhost", "127.0.0.1", "::1", "[::1]", "100.121.244.5", "192.168.100.95"}
_LOCALES |= {h.strip() for h in os.environ.get("VIGIA_HOSTS", "").split(",") if h.strip()}


def _es_local(request) -> bool:
    host = (request.get_host() or "").split(":")[0].strip().lower()
    if host not in _LOCALES:
        # Cualquier IP privada también entra: el tailnet y la LAN cambian de
        # número más seguido que este archivo.
        try:
            if not ipaddress.ip_address(host).is_private:
                return False
        except ValueError:
            return False
    # Segundo candado: si viene proxeada, viene de internet.
    return not request.META.get("HTTP_X_FORWARDED_FOR")


def _solo_local(request) -> None:
    if not _es_local(request):
        # 404 y no 403: desde fuera, la ruta no existe.
        raise Http404("El Vigía sólo se atiende en la máquina que vigila.")


# ── Página ───────────────────────────────────────────────────────────────────

@require_safe
def vivo(request):
    """El armazón. Cada panel se rellena y se refresca por su cuenta, así que si
    uno se cae (el socket de Docker, la base) los demás siguen vivos."""
    _solo_local(request)
    return render(request, "site/vivo.html", {"host_pedido": request.get_host()})


# ── Paneles ──────────────────────────────────────────────────────────────────

@require_safe
def vivo_fierro(request):
    """CPU, memoria, disco y contenedores de ESTA máquina. Refresca cada 5 s."""
    _solo_local(request)
    ctx = {"infra": {"disponible": False}}
    try:
        ctx["infra"] = snapshot_gauges_minimo()
    except Exception as exc:  # noqa: BLE001 — la pantalla nunca se cae
        ctx["error"] = str(exc)[:200]
    return render(request, "site/vivo/_fierro.html", ctx)


@require_safe
def vivo_peticiones(request):
    """El flujo de peticiones de los tres servicios. Refresca cada 2 s."""
    _solo_local(request)
    filas: list = []
    error = ""
    try:
        filas = actividad.peticiones(limite=28)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:200]
    return render(request, "site/vivo/_peticiones.html", {
        "filas": filas,
        "resumen": actividad.resumen(filas),
        "error": error,
    })


@require_safe
def vivo_contenedores(request):
    """CPU y memoria por contenedor, al estilo `docker stats`. Cada 3 s."""
    _solo_local(request)
    filas: list = []
    error = ""
    try:
        filas = contenedores.estadisticas()
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:200]
    return render(request, "site/vivo/_contenedores.html", {"filas": filas, "error": error})


@require_safe
def vivo_negocio(request):
    """Qué está haciendo el sistema POR EL DESPACHO, no por la máquina.
    Cada 20 s: son consultas a la base, no hace falta más seguido."""
    _solo_local(request)
    ctx: dict = {}
    try:
        ctx["internos"] = internos.snapshot()
    except Exception:  # noqa: BLE001
        ctx["internos"] = {}
    ctx["ia"] = _ia_hoy()
    ctx["medios"] = _medios()
    return render(request, "site/vivo/_negocio.html", ctx)


def _ia_hoy() -> dict:
    """Llamadas a Los Chalanes de hoy, con su costo. Nunca lanza."""
    try:
        from django.db.models import Count, Q, Sum
        from django.utils import timezone

        from ajustes.models.analistas_log import AnalistaLog

        inicio = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = AnalistaLog.objects.filter(creado_en__gte=inicio)
        agg = qs.aggregate(
            n=Count("id"),
            entrada=Sum("prompt_tokens"),
            salida=Sum("completion_tokens"),
            costo=Sum("costo_usd_estimado"),
            fallos=Count("id", filter=Q(exito=False)),
        )
        ultima = qs.order_by("-creado_en").values(
            "provider", "modelo", "estacion", "latencia_ms", "exito", "creado_en",
        ).first()
        return {
            "disponible": True,
            "llamadas": agg["n"] or 0,
            "tokens": (agg["entrada"] or 0) + (agg["salida"] or 0),
            "costo": float(agg["costo"] or 0),
            "fallos": agg["fallos"] or 0,
            "ultima": ultima,
        }
    except Exception:  # noqa: BLE001 — columnas distintas, app no instalada
        return {"disponible": False}


def _medios() -> dict:
    """Cuántos medios guarda El Almacén y cuánto pesan. Nunca lanza."""
    try:
        from lib import almacen

        raiz = almacen.raiz()
        originales = list(raiz.glob("orig/*/*/*/archivo"))
        bytes_totales = sum(p.stat().st_size for p in originales)
        derivados = sum(1 for _ in raiz.glob("pub/*/*/*/*"))
        return {
            "disponible": True,
            "archivos": len(originales),
            "mb": round(bytes_totales / 1048576, 1),
            "derivados": derivados,
        }
    except Exception:  # noqa: BLE001 — el almacén no está montado en esta app
        return {"disponible": False}


__all__ = ["vivo", "vivo_fierro", "vivo_peticiones", "vivo_contenedores", "vivo_negocio"]
