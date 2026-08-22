"""La Limpieza — el botón que libera caché, RAM y disco desde la pantalla.

Existía ya como guion nocturno (`infra/scripts/optimizar.sh`, que corre después
del respaldo cada tres días). Esto es lo mismo **a mano**, desde El Vigía y desde
El Site, para el rato en que alguien está mirando los anillos y quiere soltar lo
que se acumuló sin tener que entrar por SSH a un servidor sin pantalla.

── Qué hace, y qué NO puede hacer desde aquí ─────────────────────────────────

Corre dentro del contenedor de La Gerencia, así que puede hacer casi todo lo del
guion nocturno: borrar el caché de la aplicación, compactar La Libreta, aspirar
la base, podar lo que Docker dejó tirado y reciclar los trabajadores de gunicorn
(que es la parte que de verdad devuelve RAM).

Lo único que NO puede es soltar el caché de páginas del sistema: eso se escribe
en `/proc/sys/vm/drop_caches`, y `/proc` está montado en sólo-lectura a
propósito. Ese paso se reporta como «no se puede desde aquí» en vez de fingir que
se hizo — y de todos modos, en una máquina con 15 G de memoria, soltar el caché
de lectura del kernel es lo menos útil de la lista (el kernel lo suelta solo
cuando alguien necesita la memoria).

── Reglas que no hay que deshacer ────────────────────────────────────────────

1. **El caché se borra por LLAVES, nunca con `cache.clear()`.** El `clear()` del
   backend de Redis de Django hace `FLUSHDB`, y en esta máquina el caché comparte
   base de datos con **la cola del Portavoz** (`portavoz:cola`, que no tiene
   caducidad), el limitador de intentos de login y las series de El Vigía. Un
   `clear()` se llevaría los eventos pendientes sin dejar rastro. Se borran sólo
   las llaves con el prefijo de Django, y hay una prueba que lo exige.

2. **Nada de aquí lanza.** Cada paso se reporta con su estado y su motivo. Un
   botón de mantenimiento que devuelve un 500 no dice qué se hizo y qué no, que
   es exactamente lo que hace falta saber.

3. **Nada borra datos.** Ni volúmenes de Docker, ni respaldos, ni derivados de El
   Almacén. Todo lo que se suelta aquí, o se recalcula solo, o ya sobraba.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from . import contenedores, host

logger = logging.getLogger(__name__)

# Dónde se guarda el resultado de la última corrida y el candado de «ya está
# corriendo». Va en Redis y no en la base porque es información de máquina, se
# consulta desde dos pantallas que refrescan solas, y no merece una migración.
LLAVE_ULTIMA = "despacho:limpieza:ultima"
LLAVE_CANDADO = "despacho:limpieza:corriendo"
VIDA_ULTIMA = 60 * 60 * 24 * 30  # un mes de memoria alcanza y sobra
VIDA_CANDADO = 180

# Umbral para compactar el registro de La Libreta, igual que el guion nocturno.
UMBRAL_AOF_MB = 64

# El presupuesto de tiempo de toda la limpieza. Gunicorn mata al trabajador que
# tarda más de 30 s en contestar (su default), y quedarse sin trabajador significa
# que el usuario ve un error aunque la limpieza SÍ haya corrido — el peor de los
# dos mundos. Así que esto se queda holgadamente por debajo: lo que no alcance se
# reporta y lo termina la siguiente corrida.
PRESUPUESTO_S = 24.0
# Y de ese presupuesto se APARTA un pedazo para el reciclado, que es lo último de
# la lista y a la vez lo único que devuelve RAM: si se repartiera por orden de
# llegada, una poda lenta se comería justo el paso que da sentido al botón.
RESERVA_RECICLADO_S = 6.0


def _redis():
    import redis

    from . import redis_status
    return redis.Redis.from_url(redis_status.REDIS_URL, socket_connect_timeout=2,
                                socket_timeout=5)


def _paso(clave: str, titulo: str, estado: str, detalle: str = "") -> dict[str, Any]:
    """Un renglón del reporte. `estado` ∈ ok · nada · no_aplica · error."""
    return {"clave": clave, "titulo": titulo, "estado": estado, "detalle": detalle}


# ── Los pasos ────────────────────────────────────────────────────────────────

def borrar_cache() -> dict[str, Any]:
    """Borra las llaves del caché de Django, y sólo ésas.

    El patrón sale del propio caché (`make_key("*")` → `:1:*`) en vez de estar
    escrito a mano: si algún día se declara un `KEY_PREFIX`, esto lo sigue solo.

    Las sesiones también se cachean (`SESSION_ENGINE = cached_db`) y aquí se
    borran, pero **nadie se sale de su sesión**: ese motor lee de la base cuando
    el caché no tiene la sesión, y la vuelve a guardar. Lo único que cuesta es
    una consulta más la primera vez.
    """
    titulo = "Caché de la aplicación"
    try:
        from django.conf import settings
        from django.core.cache import cache

        motor = (settings.CACHES.get("default", {}).get("BACKEND") or "").lower()
        if "redis" not in motor:
            return _paso("cache", titulo, "no_aplica",
                         "en esta máquina el caché no vive en La Libreta")
        patron = cache.make_key("*")
        prefijo = patron[:-1]
    except Exception as exc:  # noqa: BLE001
        return _paso("cache", titulo, "error", str(exc)[:120])

    try:
        c = _redis()
        borradas = 0
        lote: list[bytes] = []
        for llave in c.scan_iter(match=patron, count=500):
            # Cinturón y tirantes: aunque el patrón ya excluye `portavoz:*`, la
            # cola del Portavoz no se toca ni por accidente.
            texto = llave.decode("utf-8", "replace") if isinstance(llave, bytes) else str(llave)
            if not texto.startswith(prefijo) or texto.startswith("portavoz:"):
                continue
            lote.append(llave)
            if len(lote) >= 500:
                borradas += int(c.unlink(*lote) or 0)
                lote = []
        if lote:
            borradas += int(c.unlink(*lote) or 0)
    except Exception as exc:  # noqa: BLE001
        return _paso("cache", titulo, "error", str(exc)[:120])
    if not borradas:
        return _paso("cache", titulo, "nada", "ya estaba limpio")
    # El conteo va aparte del texto porque el resumen de arriba lo redacta a su
    # manera («1,204 llaves de caché»), y rearmarlo de la cadena sería frágil.
    return {**_paso("cache", titulo, "ok", f"{borradas:,} llaves borradas"),
            "n": borradas}


def compactar_libreta() -> dict[str, Any]:
    """Compacta el registro de La Libreta si creció, y le pide que devuelva la
    memoria que ya no usa.

    Dos cosas distintas: `BGREWRITEAOF` reescribe el registro en disco (eso es
    DISCO) y `MEMORY PURGE` le dice al asignador que devuelva al sistema las
    páginas que dejó libres (eso es RAM). La segunda sólo existe si Redis se
    compiló con jemalloc; si no, contesta con un error y se ignora.
    """
    titulo = "La Libreta (Redis)"
    try:
        c = _redis()
        info = c.info(section="persistence")
        mb = round((info.get("aof_current_size") or 0) / 1048576, 1)
        partes: list[str] = []
        if mb >= UMBRAL_AOF_MB:
            c.bgrewriteaof()
            partes.append(f"registro de {mb} MB compactándose")
        else:
            partes.append(f"registro en {mb} MB, no hacía falta compactarlo")
        try:
            c.execute_command("MEMORY", "PURGE")
            partes.append("memoria devuelta al sistema")
        except Exception:  # noqa: BLE001 — sin jemalloc no existe; no es un fallo
            pass
    except Exception as exc:  # noqa: BLE001
        return _paso("libreta", titulo, "error", str(exc)[:120])
    return _paso("libreta", titulo, "ok", " · ".join(partes))


def aspirar_la_base() -> dict[str, Any]:
    """`VACUUM (ANALYZE)`: libera el espacio de las filas muertas y refresca las
    estadísticas que usa el planeador para elegir sus índices.

    Va con un tiempo máximo, y no es paranoia: hoy la base pesa 29 MB y esto
    tarda milésimas, pero un `VACUUM` sobre una base de varios gigas puede
    tardar minutos, y gunicorn mata al trabajador que no contesta en 30 s.
    Quedarse a medias no hace daño —el aspirado va tabla por tabla— así que el
    corte por tiempo es la respuesta correcta y no un parche.
    """
    titulo = "El Archivero (Postgres)"
    try:
        from django.db import connection

        if not connection.get_autocommit():
            # `VACUUM` no se puede correr dentro de una transacción. Si alguien
            # pusiera `ATOMIC_REQUESTS`, esto lo dice en vez de reventar.
            return _paso("base", titulo, "no_aplica",
                         "la petición viene dentro de una transacción")
        antes_n, antes = _tamano_base(connection)
        try:
            with connection.cursor() as cur:
                cur.execute("SET statement_timeout = '10s'")
                cur.execute("VACUUM (ANALYZE)")
        finally:
            # **Obligatorio, y no es cortesía.** `CONN_MAX_AGE = 60` significa que
            # esta conexión se reusa en las peticiones siguientes: un tope de 10 s
            # olvidado aquí se le aplicaría, durante un minuto, a consultas que no
            # tienen nada que ver — y el síntoma sería «a veces un reporte truena».
            # Va en su propio intento para no tapar el error de arriba si falla.
            _quitar_tope(connection)
        despues_n, despues = _tamano_base(connection)
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        if "statement timeout" in texto.lower() or "canceling statement" in texto.lower():
            return _paso("base", titulo, "ok",
                         "se aspiró lo que alcanzó en 10 s; el resto lo termina "
                         "el guion nocturno")
        return _paso("base", titulo, "error", texto[:120])
    detalle = "filas muertas liberadas y estadísticas al día"
    # La comparación va en BYTES y no en el texto bonito: «9 MB» es mayor que
    # «31 MB» si se comparan como cadenas, y el renglón diría que la base bajó
    # cuando creció. (Y lo normal es que no se mueva: `VACUUM` sin `FULL`
    # reutiliza el espacio, no lo devuelve al sistema — por eso el caso de abajo
    # es el habitual y no el excepcional.)
    if antes_n and despues_n and despues_n < antes_n:
        detalle = f"bajó de {antes} a {despues}"
    elif despues:
        detalle = f"{detalle} · pesa {despues}"
    return _paso("base", titulo, "ok", detalle)


def _quitar_tope(connection) -> None:
    """Devuelve el tope de tiempo a su valor de siempre. Nunca lanza."""
    try:
        with connection.cursor() as cur:
            cur.execute("SET statement_timeout = DEFAULT")
    except Exception as exc:  # noqa: BLE001
        logger.warning("La Limpieza no pudo devolver statement_timeout: %s", exc)


def _tamano_base(connection) -> tuple[int | None, str]:
    """Cuánto pesa la base: (bytes, texto legible). `(None, "")` si no se sabe.

    Los bytes son para comparar y el texto para mostrar. Son dos cosas
    distintas, y confundirlas fue justo el defecto: comparar «9 MB» con «31 MB»
    como cadenas dice que la base bajó cuando creció.
    """
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database()), "
                        "pg_size_pretty(pg_database_size(current_database()))")
            fila = cur.fetchone()
        if not fila:
            return None, ""
        crudo = fila[0]
        return (int(crudo) if crudo is not None else None), str(fila[1] or "")
    except Exception:  # noqa: BLE001 — sin Postgres (SQLite en pruebas) no hay tamaño
        return None, ""


def podar_disco(*, presupuesto_s: float = 12.0) -> tuple[dict[str, Any], int]:
    """Lo que Docker dejó tirado: contenedores parados, imágenes colgantes, redes
    huérfanas y caché de construcción. **Nunca volúmenes** (ahí viven los datos).

    Devuelve el renglón del reporte y los bytes liberados, que se muestran arriba
    como el número grande de la limpieza: es lo único medible de verdad.
    """
    titulo = "Lo que Docker dejó tirado"
    res = contenedores.podar(presupuesto_s=presupuesto_s)
    if not res.get("disponible"):
        return _paso("disco", titulo, "no_aplica", res.get("motivo", "")), 0
    bytes_ = int(res.get("liberado_bytes") or 0)
    partes = list(res.get("detalle") or [])
    fallos = res.get("fallos") or []
    # Si no se liberó nada Y además falló todo, el paso NO es «ok»: decir «0 MB
    # liberados» con un «con problemas» al final se lee como que salió bien.
    if not bytes_ and not partes:
        if fallos:
            return _paso("disco", titulo, "error", "; ".join(fallos[:2])), 0
        return _paso("disco", titulo, "nada", "no había nada que podar"), 0
    if fallos:
        partes.append("con problemas: " + "; ".join(fallos[:2]))
    detalle = f"{res.get('liberado_mb')} MB liberados"
    if partes:
        detalle += " · " + " · ".join(partes)
    return _paso("disco", titulo, "ok", detalle), bytes_


def reciclar_trabajadores() -> dict[str, Any]:
    """Recicla los trabajadores de gunicorn: es la parte que devuelve RAM.

    No hay corte de servicio — ver el detalle en
    `lib.site.contenedores.reciclar_trabajadores`, incluida la razón por la que
    la señal va por dentro y **nunca** con `docker kill`.
    """
    titulo = "Reciclar los trabajadores"
    res = contenedores.reciclar_trabajadores(presupuesto_s=RESERVA_RECICLADO_S)
    if not res.get("disponible"):
        return _paso("memoria", titulo, "no_aplica", res.get("motivo", ""))
    hechos = res.get("reciclados") or []
    if not hechos:
        fallos = "; ".join(res.get("fallos") or [])
        return _paso("memoria", titulo, "nada" if not fallos else "error",
                     fallos or "no había apps corriendo")
    detalle = (", ".join(hechos) +
               " · la memoria baja conforme los trabajadores nuevos toman el relevo")
    if res.get("fallos"):
        detalle += " · con problemas: " + "; ".join(res["fallos"][:2])
    return _paso("memoria", titulo, "ok", detalle)


def soltar_paginas() -> dict[str, Any]:
    """El caché de páginas del sistema. Casi siempre «no se puede desde aquí».

    Se escribe en `/proc/sys/vm/drop_caches`, y `/proc` se monta en sólo-lectura
    a propósito: dejarlo escribible sólo para esto le abriría al contenedor todos
    los parámetros del kernel. El guion nocturno, que corre en el host como root,
    sí lo hace. La comprobación es la misma que la suya (`-w`).
    """
    titulo = "Caché de disco del sistema"
    ruta = host.PROC_ROOT / "sys" / "vm" / "drop_caches"
    if not os.access(ruta, os.W_OK):
        return _paso("paginas", titulo, "no_aplica",
                     "el sistema no deja escribir /proc desde aquí; el guion "
                     "nocturno sí lo suelta")
    try:
        os.sync()
        with open(ruta, "w") as f:
            f.write("3")
    except OSError as exc:
        return _paso("paginas", titulo, "error", str(exc)[:120])
    return _paso("paginas", titulo, "ok", "caché de lectura soltado")


# ── La corrida completa ──────────────────────────────────────────────────────

def limpiar(*, quien: str = "") -> dict[str, Any]:
    """Corre la limpieza y guarda el resultado. Nunca lanza.

    Si otra corrida está en curso devuelve `{"ocupado": True}`: dos limpiezas a
    la vez no se estorban de forma peligrosa, pero sí se pisan los números del
    reporte y no tiene sentido.
    """
    candado = _tomar_candado()
    if candado is False:
        return {"ocupado": True}
    arranque = time.monotonic()
    antes = _foto_de_la_maquina()
    pasos: list[dict[str, Any]] = []
    liberado = 0
    try:
        pasos.append(borrar_cache())
        pasos.append(compactar_libreta())
        pasos.append(aspirar_la_base())
        gastado = time.monotonic() - arranque
        para_podar = max(PRESUPUESTO_S - RESERVA_RECICLADO_S - gastado, 0.0)
        paso_disco, liberado = podar_disco(presupuesto_s=para_podar)
        pasos.append(paso_disco)
        # El reciclado va al final: es lo único que toca el proceso que está
        # atendiendo esta misma petición.
        pasos.append(reciclar_trabajadores())
        pasos.append(soltar_paginas())
    except Exception as exc:  # noqa: BLE001 — pase lo que pase, se reporta
        logger.warning("La Limpieza tropezó: %s", exc)
        pasos.append(_paso("interrumpida", "La limpieza se interrumpió", "error",
                           str(exc)[:120]))
    finally:
        _soltar_candado()

    resultado = {
        "cuando": _ahora_iso(),
        "quien": quien or "la pared",
        "segundos": round(time.monotonic() - arranque, 1),
        "liberado_mb": round(liberado / 1048576, 1),
        "antes": antes,
        "despues": _foto_de_la_maquina(),
        "pasos": pasos,
        "problemas": sum(1 for p in pasos if p["estado"] == "error"),
    }
    resultado["resumen"] = _resumir(resultado)
    _guardar(resultado)
    return resultado


def ultima() -> dict[str, Any]:
    """El resultado de la última limpieza, o `{}`. Nunca lanza.

    Se lee de Redis en cada pintado del panel para que la respuesta al botón y
    el refresco automático digan lo mismo: si esto viviera en la respuesta del
    POST, el siguiente refresco (cada 5 s en la pared) lo borraría de la
    pantalla.
    """
    try:
        crudo = _redis().get(LLAVE_ULTIMA)
    except Exception:  # noqa: BLE001
        return {}
    if not crudo:
        return {}
    try:
        return json.loads(crudo)
    except (TypeError, ValueError):
        return {}


def corriendo() -> bool:
    try:
        return bool(_redis().exists(LLAVE_CANDADO))
    except Exception:  # noqa: BLE001
        return False


# ── Plomería ─────────────────────────────────────────────────────────────────

def _tomar_candado() -> bool | None:
    """True si se tomó, False si ya había otra corrida, None si no hay Redis.

    Sin Redis se deja pasar: el candado es una cortesía, no una barrera, y
    negarle el botón a alguien porque Redis no contesta sería peor.
    """
    try:
        return bool(_redis().set(LLAVE_CANDADO, "1", nx=True, ex=VIDA_CANDADO))
    except Exception:  # noqa: BLE001
        return None


def _soltar_candado() -> None:
    try:
        _redis().delete(LLAVE_CANDADO)
    except Exception:  # noqa: BLE001
        return


def _guardar(resultado: dict[str, Any]) -> None:
    try:
        _redis().set(LLAVE_ULTIMA, json.dumps(resultado), ex=VIDA_ULTIMA)
    except Exception:  # noqa: BLE001
        return


def _ahora_iso() -> str:
    from lib.fecha import ahora_mx
    return ahora_mx().isoformat()


def _foto_de_la_maquina() -> dict[str, Any]:
    """Memoria y disco libres, en gigas. Para el antes y el después."""
    try:
        m = host.memoria()
        d = host.disco()
        return {
            "ram_libre_gb": round((m.get("libre_mb") or 0) / 1024, 1) if m.get("disponible") else None,
            "disco_libre_gb": d.get("libre_gb") if d.get("disponible") else None,
        }
    except Exception:  # noqa: BLE001
        return {}


def _resumir(r: dict[str, Any]) -> str:
    """Una línea en llano. Lo que se lee de lejos en la pared."""
    def _de(clave: str) -> dict[str, Any] | None:
        return next((p for p in r["pasos"] if p["clave"] == clave), None)

    piezas: list[str] = []
    if r.get("liberado_mb"):
        piezas.append(f"{r['liberado_mb']} MB de disco")
    cache = _de("cache")
    if cache and cache.get("n"):
        piezas.append(f"{cache['n']:,} llaves de caché")
    memoria = _de("memoria")
    if memoria and memoria["estado"] == "ok":
        piezas.append("trabajadores reciclados")

    linea = "liberó " + ", ".join(piezas) if piezas else "no había nada que soltar"
    problemas = r.get("problemas") or 0
    if problemas:
        # «1 paso(s)» se lee como un error de programa. Si va a leerlo una
        # persona, se conjuga.
        linea += f" · {problemas} paso{'s' if problemas > 1 else ''} con problemas"
    return linea


__all__ = [
    "LLAVE_CANDADO",
    "LLAVE_ULTIMA",
    "PRESUPUESTO_S",
    "UMBRAL_AOF_MB",
    "aspirar_la_base",
    "borrar_cache",
    "compactar_libreta",
    "corriendo",
    "limpiar",
    "podar_disco",
    "reciclar_trabajadores",
    "soltar_paginas",
    "ultima",
]
