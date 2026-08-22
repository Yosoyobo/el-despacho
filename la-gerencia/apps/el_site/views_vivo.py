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
import time
from datetime import datetime

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from lib.site import actividad, contenedores, internos, pulso
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

    # La propia pantalla deja el punto: no hay cron muestreando. Si nadie mira,
    # no se acumula nada, que es lo correcto — la serie existe para la pared.
    infra = ctx["infra"] or {}
    g = infra.get("gauges") or {}
    pulso.anotar_varias({
        "cpu": (g.get("cpu") or {}).get("pct"),
        "mem": (g.get("mem") or {}).get("pct"),
        "disco": (g.get("disk") or {}).get("pct"),
    })
    series = pulso.leer_varias(["cpu", "mem", "disco", "peticiones"])
    ctx["trazos"] = {
        # Los porcentajes con tope 100 para que la línea diga la verdad: al 20%
        # se ve baja. Con el máximo tomado del dato, un 20% plano llenaría la
        # gráfica y parecería saturación.
        "cpu": pulso.area(series["cpu"], maximo=100),
        "mem": pulso.area(series["mem"], maximo=100),
        "disco": pulso.area(series["disco"], maximo=100),
        # Las peticiones sí van con escala propia: importa el relieve, no el tope.
        "peticiones": pulso.area(series["peticiones"]),
    }
    ctx["puntos_peticiones"] = [p for p in series["peticiones"] if p is not None]
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
    res = actividad.resumen(filas)
    # Cuántas se atendieron en el último minuto: es el punto de la gráfica de
    # carga real del sistema, y se saca de las marcas que ya tenemos.
    ahora = timezone.now()
    ultimo_min = sum(
        1 for f in filas
        if f.get("cuando") and (ahora - f["cuando"]).total_seconds() <= 60
    )
    pulso.anotar("peticiones", ultimo_min)
    res["por_minuto"] = ultimo_min
    return render(request, "site/vivo/_peticiones.html", {
        "filas": filas,
        "resumen": res,
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
def vivo_chalanes(request):
    """Los Chalanes: qué se les está pidiendo, quién, y cuánto va costando.

    **Sin una sola palabra del contenido.** El log de IA guarda únicamente el
    SHA-256 del prompt (decisión reafirmada del proyecto: `AnalistaLog` no tiene
    campos de prompt ni de respuesta cruda). Lo que se audita es quién pidió,
    cuándo, a qué Chalán, con qué modelo, cuánto tardó, cuántos tokens y cuánto
    costó. Eso alcanza para vigilar el gasto y cazar un Chalán que falla, y no
    pone en una pared lo que alguien escribió.

    Cada 15 s: son consultas a la base y el gasto no cambia por segundo.
    """
    _solo_local(request)
    ctx: dict = {"llamadas": [], "por_chalan": [], "hoy": _ia_hoy()}
    try:
        from django.db.models import Count, DecimalField, Q, Sum
        from django.db.models.functions import Coalesce

        from ajustes.models.analistas_log import AnalistaLog

        desde = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)

        # Las últimas llamadas, con su actor. `select_related` porque si no son
        # N consultas para pintar N renglones.
        ctx["llamadas"] = [
            {
                "cuando": r.creado_en,
                "quien": (getattr(r.actor, "nombre_completo", "") or
                          getattr(r.actor, "email", "") or "el sistema"),
                "estacion": r.estacion.replace("_", " "),
                "chalan": _APODO_CHALAN.get(r.provider, r.provider),
                "modelo": r.modelo or "—",
                "ms": r.latencia_ms,
                "tokens": (r.prompt_tokens or 0) + (r.completion_tokens or 0),
                "costo": r.costo_usd_estimado,
                "exito": r.exito,
                "error": (r.mensaje_error or "")[:70],
                "fallback": r.es_fallback,
                # El hash se muestra a propósito: es la prueba de que la
                # auditoría existe sin exponer lo que se escribió.
                "huella": (r.prompt_hash or "")[:8],
            }
            for r in AnalistaLog.objects.select_related("actor")
            .order_by("-creado_en")[:14]
        ]

        # Y el reparto del gasto del día, para la dona.
        agg = (
            AnalistaLog.objects.filter(creado_en__gte=desde)
            .values("provider")
            .annotate(
                n=Count("id"),
                fallos=Count("id", filter=Q(exito=False)),
                costo=Coalesce(Sum("costo_usd_estimado"),
                               0, output_field=DecimalField(max_digits=12, decimal_places=6)),
                tokens=Coalesce(Sum("prompt_tokens"), 0) + Coalesce(Sum("completion_tokens"), 0),
            )
            .order_by("-n")
        )
        filas = list(agg)
        total = sum(f["n"] for f in filas) or 1
        ctx["por_chalan"] = [
            {
                "chalan": _APODO_CHALAN.get(f["provider"], f["provider"]),
                "n": f["n"],
                "fallos": f["fallos"],
                "costo": f["costo"],
                "tokens": f["tokens"],
                "pct": round(f["n"] / total * 100),
                "color": _COLOR_CHALAN.get(f["provider"], "#98a2b3"),
            }
            for f in filas
        ]
    except Exception as exc:  # noqa: BLE001 — la pared nunca se cae por esto
        ctx["error"] = str(exc)[:200]
    return render(request, "site/vivo/_chalanes.html", ctx)


@require_safe
def vivo_ventana(request):
    """La Sede: el Droplet que da la cara a internet.

    Desde la mudanza, el droplet ya no corre el sistema — sólo termina el TLS y
    reenvía por el tailnet. Pero sigue siendo la puerta: si se cae, nadie entra
    aunque el NUC esté perfecto. Por eso se vigila aparte y con su propia cara.

    Cada 30 s: son llamadas por internet (DigitalOcean y las dos sondas) y no
    tiene sentido machacarlas.
    """
    _solo_local(request)
    ctx: dict = {}
    try:
        from lib.site import droplet
        ctx["do"] = droplet.info_remota()
        ctx["local"] = droplet.info_local()
    except Exception as exc:  # noqa: BLE001
        ctx["do"] = {"disponible": False, "motivo": str(exc)[:120]}
        ctx["local"] = {}
    ctx["puertas"] = _sondear_puertas()
    return render(request, "site/vivo/_ventana.html", ctx)


# Los proveedores de IA tienen nombre en el proyecto; el slug técnico no se
# muestra. Si entra uno nuevo y no está aquí, cae a su slug — visible pero feo,
# que es la señal correcta para venir a agregarlo.
_APODO_CHALAN = {
    "anthropic": "Claudio",
    "openai": "GPT",
    "deepseek": "Chino",
    "mimo": "MiMo",
    "gemini": "Gemini",
    "grok": "Grok",
}
_COLOR_CHALAN = {
    "anthropic": "#465fff",   # brand
    "openai": "#32d583",      # success
    "deepseek": "#fdb022",    # warning
    "mimo": "#36bffa",        # blue-light
    "gemini": "#fb6514",      # orange
    "grok": "#f97066",        # error
}


def _sondear_puertas() -> list[dict]:
    """Las tres puertas de internet, vistas desde aquí. Nunca lanza.

    Se piden en paralelo: en serie, tres tiempos de espera se suman y el panel
    tardaría hasta 15 s en pintar.
    """
    import httpx

    objetivos = (
        ("El Taller", "https://taller.learningcenter.mx/ping"),
        ("La Gerencia", "https://gerencia.learningcenter.mx/ping"),
        ("El sitio", "https://learningcenter.mx/"),
    )

    def una(par):
        nombre, url = par
        try:
            t0 = time.monotonic()
            r = httpx.get(url, timeout=5.0, follow_redirects=True)
            return {"nombre": nombre, "codigo": r.status_code,
                    "ms": int((time.monotonic() - t0) * 1000),
                    "ok": 200 <= r.status_code < 400}
        except Exception:  # noqa: BLE001 — sin internet, la puerta sale caída
            return {"nombre": nombre, "codigo": None, "ms": None, "ok": False}

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(una, objetivos))


@require_safe
def vivo_negocio(request):
    """Qué está haciendo el sistema POR EL DESPACHO, no por la máquina.
    Cada 20 s: son consultas a la base, no hace falta más seguido."""
    _solo_local(request)
    ctx: dict = {}
    try:
        ctx["internos"] = _fechas_locales(internos.snapshot())
    except Exception:  # noqa: BLE001
        ctx["internos"] = {}
    ctx["ia"] = _ia_hoy()
    ctx["medios"] = _medios()
    return render(request, "site/vivo/_negocio.html", ctx)


def _cuando(iso: str | None) -> str:
    """Una marca ISO en UTC, pasada a hora local y legible.

    `internos.snapshot()` entrega las fechas como `isoformat()` de un datetime
    aware, o sea en UTC. La plantilla las rebanaba con `slice:":16"|cut:"T"`, lo
    que producía dos errores a la vez: pegaba la fecha a la hora
    ("2026-08-2205:03") y, peor, **dejaba la hora en UTC** mientras el reloj de
    la cabecera va en hora local. Dos relojes en zonas distintas en la misma
    pared es una trampa: se lee "el respaldo corrió a las 5 de la mañana"
    cuando en realidad fueron las 11 de la noche.
    """
    if not iso:
        return ""
    try:
        cuando = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)[:16]
    if timezone.is_aware(cuando):
        cuando = timezone.localtime(cuando)
    return cuando.strftime("%d/%m %H:%M")


def _fechas_locales(snap: dict) -> dict:
    """Deja las marcas de `internos` listas para pintar, y el hash corto.

    El commit venía completo (64 caracteres) y se comía el renglón; siete
    bastan para identificarlo, que es para lo que se mira en una pared.
    """
    for llave in ("backup_remoto", "backup_local", "deploy", "portavoz_head"):
        bloque = snap.get(llave)
        if isinstance(bloque, dict):
            if bloque.get("creado_en"):
                bloque["cuando"] = _cuando(bloque["creado_en"])
            if bloque.get("commit"):
                bloque["commit_corto"] = str(bloque["commit"])[:7]
    return snap


def _ia_hoy() -> dict:
    """Llamadas a Los Chalanes de hoy, con su costo. Nunca lanza."""
    try:
        from django.db.models import Count, Q, Sum

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
