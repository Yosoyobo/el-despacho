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
from datetime import UTC, datetime

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
    # Ojo con los nombres: `snapshot_gauges_minimo()` los devuelve en español
    # —`memoria`, `disco`— y la primera versión de esto pedía `mem` y `disk`. El
    # `.get()` devolvía None sin quejarse, así que las dos series se guardaban
    # vacías y las gráficas decían «midiendo la tendencia…» para siempre. Un
    # `.get()` con la llave equivocada no falla: miente en silencio.
    io = (infra.get("host") or {}).get("disco_io") or {}
    pulso.anotar_varias({
        "cpu": (g.get("cpu") or {}).get("pct"),
        "mem": (g.get("memoria") or {}).get("pct"),
        # Del disco se guarda su ACTIVIDAD, no su porcentaje ocupado: ese último
        # es 14.5% hoy y 14.5% mañana, y una línea plana no dice nada. Lo que se
        # mueve —y lo que interesa— es cuánto está trabajando.
        "disco_lee": io.get("lectura_mb_s"),
        "disco_escribe": io.get("escritura_mb_s"),
    })
    # La memoria en GIGAS, no en megas. «3933.8 MB usados» obliga a dividir
    # mentalmente para saber si son muchos o pocos; «3.8 de 15 GB» se entiende de
    # un vistazo, que es todo lo que se le pide a una pared.
    mem = (infra.get("host") or {}).get("memoria") or {}
    if mem.get("disponible"):
        ctx["mem_gb"] = {
            "usado": round((mem.get("usado_mb") or 0) / 1024, 1),
            "libre": round((mem.get("libre_mb") or 0) / 1024, 1),
            "total": round((mem.get("total_mb") or 0) / 1024, 1),
        }

    series = pulso.leer_varias(
        ["cpu", "mem", "disco_lee", "disco_escribe", "peticiones"]
    )
    # `relieve=True` en CPU y memoria porque son las dos que se mueven POCO y en
    # rangos estrechos: con el eje de 0 a 100, una memoria oscilando entre 25.4% y
    # 25.9% sale como una raya recta y parece que no pasa nada. Con el eje
    # ajustado a la propia serie, ese medio punto se ve como la pendiente que es.
    # No engaña: el número absoluto va al lado, grande.
    ctx["trazos"] = {
        "cpu": pulso.area(series["cpu"], relieve=True),
        "mem": pulso.area(series["mem"], relieve=True),
        # La actividad del disco sí arranca en cero de verdad, así que su eje
        # empieza en cero: un pico se tiene que ver como un pico.
        "disco_lee": pulso.area(series["disco_lee"]),
        "disco_escribe": pulso.area(series["disco_escribe"]),
    }
    # El pie de la tarjeta del disco se arma AQUÍ y no en la plantilla. Encadenar
    # seis filtros para pegar dos números es ilegible, y además era un 500: pasar
    # `io.escritura_mb_s` como ARGUMENTO de `add:` hace que Django lo resuelva
    # SIN silenciar el fallo (los argumentos de filtro no se silencian, a
    # diferencia de las variables sueltas). Con `disco_io` en su primera muestra
    # —«disponible: False»— esa llave no existe y la página revienta. O sea que
    # fallaba SÓLO en el primer refresco tras recrear el contenedor, que es el
    # peor momento para descubrirlo.
    ctx["io"] = io

    # Los textos de las cuatro tarjetas se arman AQUÍ, todos. Es más legible que
    # encadenar seis filtros en la plantilla, y sobre todo evita el 500: pasar
    # `algo.llave` como ARGUMENTO de `add:` hace que Django lo resuelva SIN
    # silenciar el fallo (los argumentos de filtro no se silencian, a diferencia
    # de las variables sueltas), así que una llave ausente revienta la página.
    # Pasaba con `disco_io` en su primera muestra, y estaba LATENTE en las otras
    # tres: si `/proc` no se monta, `memoria`/`disco`/`cpu_load` devuelven sólo
    # `{disponible: False}` y las tres tarjetas se caían igual.
    cpu = (infra.get("host") or {}).get("cpu_load") or {}
    disco = (infra.get("host") or {}).get("disco") or {}
    gb = ctx.get("mem_gb") or {}

    def _num(v, sufijo=""):
        return f"{v}{sufijo}" if v is not None else "—"

    # El color del anillo de memoria lo decide el COLCHÓN, no el porcentaje. Un
    # 70% de 14.8 G deja 4.4 G libres y está perfecto; un 70% de 4 G no. Lo que
    # importa es cuánto queda, no qué proporción se usó — y así el anillo se pone
    # rojo el día en que de verdad hay que hacer algo, no antes.
    presion = (infra.get("host") or {}).get("presion") or {}
    if presion.get("disponible"):
        g = dict(g)
        mem = dict(g.get("memoria") or {})
        mem["color"] = {"ok": "success", "aviso": "warning",
                        "falla": "error"}.get(presion.get("estado"), "success")
        g["memoria"] = mem
        ctx["infra"] = {**infra, "gauges": g}
    ctx["presion"] = presion

    ctx["textos"] = {
        "cpu_a": _num(cpu.get("cores"), " núcleos activos"),
        "cpu_b": f"5 min: {cpu.get('load_5')}" if cpu.get("load_5") is not None else "",
        "mem_unidad": f"de {gb.get('total')} GB" if gb.get("total") else "GB",
        "mem_a": (presion.get("detalle") if presion.get("estado") != "ok"
                  else _num(gb.get("libre"), " GB libres")),
        "disco_unidad": (f"de {disco.get('total_gb')} GB"
                         if disco.get("total_gb") is not None else "GB"),
        "disco_a": _num(disco.get("libre_gb"), " GB libres"),
        "disco_b": (f"{io.get('lectura_mb_s')} lee · {io.get('escritura_mb_s')} escribe MB/s"
                    if io.get("disponible") else ""),
    }
    # Las peticiones van en barras: es un conteo discreto que toca el cero
    # seguido, y un área con huecos se ve como trozos sueltos en vez de un ritmo.
    # Se toman los últimos 32 puntos porque más barras en ese ancho quedan de un
    # píxel y no se distingue nada.
    recientes = series["peticiones"][-32:]
    tope = max([p for p in recientes if p is not None] or [1]) or 1
    ctx["barras_peticiones"] = [
        {"n": int(p or 0), "pct": round((p or 0) / tope * 100)}
        for p in recientes
    ] if len(recientes) >= 2 else []
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


def _trabajo_del_despacho() -> dict:
    """Lo que el despacho tiene entre manos AHORA. Nunca lanza.

    El panel mostraba sólo infraestructura —el almacén, la cola, el respaldo, el
    último despliegue— que es información de la máquina, no del negocio. En una
    pared del taller lo que importa es cuántos proyectos hay vivos y qué está
    esperando a alguien.

    Las consultas son conteos sobre columnas indexadas y van juntas en un solo
    viaje mental: si alguna falla, ese renglón sale vacío y los demás siguen.
    """
    salida: dict = {}
    try:
        from apps.el_pizarron.models.tarea import Tarea
        from apps.los_proyectos.models.estado import EstadoProyecto
        from apps.los_proyectos.models.proyecto import Proyecto
        from django.utils import timezone as _tz

        # Los estados terminales salen del catálogo, no de una lista escrita a
        # mano: si el super_admin agrega uno, la cuenta lo respeta sola.
        terminales = list(
            EstadoProyecto.objects.filter(terminal=True).values_list("slug", flat=True)
        )
        vivos = Proyecto.objects.filter(archivado=False).exclude(estado__in=terminales)
        salida["proyectos"] = vivos.count()
        salida["por_cotizar"] = vivos.filter(estado="por_cotizar").count()

        # Los cancelados: no están en `vivos` (su estado es terminal) así que se
        # cuentan aparte. Van los del mes en curso y no el total histórico:
        # «183 cancelados desde siempre» no dice nada, «4 este mes» sí — es el
        # número que hace preguntar por qué.
        hoy = _tz.localdate()
        primero = hoy.replace(day=1)
        cancelados = Proyecto.objects.filter(archivado=False, estado="cancelado")
        salida["cancelados_mes"] = cancelados.filter(
            cancelado_en__date__gte=primero
        ).count()
        salida["cancelados"] = cancelados.count()
        pendientes = Tarea.objects.filter(archivada=False).exclude(
            estado__in=list(
                __import__("apps.el_pizarron.models.estado_tarea", fromlist=["EstadoTarea"])
                .EstadoTarea.objects.filter(terminal=True)
                .values_list("slug", flat=True)
            )
        )
        salida["tareas"] = pendientes.count()
        salida["atrasadas"] = pendientes.filter(fecha_compromiso__lt=hoy).count()
    except Exception:  # noqa: BLE001 — la pared nunca se cae por un conteo
        pass

    try:
        from apps.facturacion.models.factura import Factura
        porcobrar = Factura.vigentes.filter(estado__in=("emitida", "cobrada_parcial"))
        salida["facturas"] = porcobrar.count()
        salida["monto_por_cobrar"] = sum((f.saldo_pendiente or 0) for f in porcobrar)
    except Exception:  # noqa: BLE001
        pass
    return salida


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
    ctx["trabajo"] = _trabajo_del_despacho()
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
    for llave in ("backup_remoto", "backup_medios", "backup_local",
                  "deploy", "portavoz_head"):
        bloque = snap.get(llave)
        if not isinstance(bloque, dict):
            continue
        if bloque.get("creado_en"):
            bloque["cuando"] = _cuando(bloque["creado_en"])
        # El respaldo local no guarda un ISO: trae la marca del archivo en disco.
        elif bloque.get("creado_en_ts"):
            bloque["cuando"] = _cuando(
                datetime.fromtimestamp(bloque["creado_en_ts"], tz=UTC).isoformat()
            )
        if bloque.get("commit"):
            bloque["commit_corto"] = str(bloque["commit"])[:7]
        # El tamaño en la unidad que se lee. «449106 bytes» no le dice nada a
        # nadie desde una pared, y «0.4 MB» tampoco: en KB se ve que hay algo.
        # Importa porque es justo el número que delata un respaldo vacío — pasó
        # con un dump de 20 bytes que llegó a HAL pareciendo copia buena.
        n = bloque.get("tamano_bytes")
        if n:
            bloque["peso"] = (f"{n / 1048576:.1f} MB" if n >= 1048576
                              else f"{n / 1024:.0f} KB")
        elif n == 0:
            # Un cero explícito es una alarma, no un dato: se dice con palabras.
            bloque["peso"] = "vacío"
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
