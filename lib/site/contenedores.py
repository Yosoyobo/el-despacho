"""Cliente mínimo sobre el socket de Docker (UNIX). Lee containers, su estado
y stats básicos. No depende de la SDK de docker (`pip install docker`) ni del
CLI — solo stdlib.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
from typing import Any

DOCKER_SOCK = os.environ.get("SITE_DOCKER_SOCK", "/var/run/docker.sock")


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, sock_path: str, timeout: float = 3.0):
        super().__init__("localhost", timeout=timeout)
        self._sock_path = sock_path

    def connect(self) -> None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._sock_path)
        self.sock = s


def _get(path: str, *, sock: str | None = None, timeout: float = 3.0) -> Any:
    conn = _UnixHTTPConnection(sock or DOCKER_SOCK, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status >= 400:
            raise RuntimeError(f"docker API {resp.status}: {body[:200]!r}")
        return json.loads(body) if body else None
    finally:
        conn.close()


def disponible() -> bool:
    return os.path.exists(DOCKER_SOCK)


def info() -> dict[str, Any]:
    if not disponible():
        return {"disponible": False}
    try:
        d = _get("/v1.44/info")
    except Exception as exc:  # noqa: BLE001
        return {"disponible": False, "error": str(exc)[:200]}
    return {
        "disponible": True,
        "containers": d.get("Containers"),
        "running": d.get("ContainersRunning"),
        "stopped": d.get("ContainersStopped"),
        "imagenes": d.get("Images"),
        "version_servidor": d.get("ServerVersion"),
        "kernel": d.get("KernelVersion"),
    }


def listar() -> list[dict[str, Any]]:
    """Lista de containers con estado simplificado. Vacío si no hay socket."""
    if not disponible():
        return []
    try:
        rows = _get("/v1.44/containers/json?all=1")
    except Exception:
        return []
    out = []
    for r in rows or []:
        names = r.get("Names") or []
        nombre = (names[0] if names else "").lstrip("/")
        out.append({
            "id": (r.get("Id") or "")[:12],
            "nombre": nombre,
            "imagen": r.get("Image"),
            "estado": r.get("State"),  # running, exited, ...
            "estado_humano": r.get("Status"),
            "creado_ts": r.get("Created"),
        })
    return out


def snapshot() -> dict[str, Any]:
    return {"info": info(), "containers": listar()}

# ── Estadísticas por contenedor ───────────────────────────────────────────────
# El endpoint `/stats` de Docker, con `stream=false` a secas, **espera ~1 segundo**
# porque toma DOS muestras para poder calcular el CPU. Con seis contenedores eso
# son seis segundos por refresco: inservible para una pantalla en vivo.
#
# `one-shot=true` responde al instante, pero deja `precpu_stats` en cero y el CPU
# no se puede derivar de una sola muestra. La salida: guardar la muestra anterior
# en el proceso y calcular el delta contra ella — que es exactamente lo que hace
# `docker stats`. El primer refresco tras arrancar muestra CPU en blanco; del
# segundo en adelante, real.
# Los nombres de contenedor son estériles («despacho-gerencia», «postgres») y no
# dicen nada a quien mira la pared. Cada pieza de El Despacho tiene su nombre y
# su oficio: se muestran ésos, con el técnico disponible por si hace falta.
_PIEZAS: tuple[tuple[str, str, str], ...] = (
    # (fragmento del nombre del contenedor, cómo se llama, qué hace)
    ("el-taller",       "El Taller",     "donde trabaja el equipo"),
    ("gerencia",        "La Gerencia",   "ajustes y catálogos"),
    ("recepcion",       "La Recepción",  "portal de clientes"),
    ("mostrador",       "El Mostrador",  "entrega las fotos"),
    ("portavoz",        "El Portavoz",   "avisa a los sistemas de fuera"),
    ("postgres",        "El Archivero",  "guarda todo"),
    ("redis",           "La Libreta",    "notas rápidas y la cola"),
    ("portero",         "El Portero",    "recibe de internet"),
)


def bautizar(nombre_contenedor: str) -> tuple[str, str]:
    """De «despacho-gerencia» a («La Gerencia», «ajustes y catálogos»)."""
    n = (nombre_contenedor or "").lower()
    for fragmento, nombre, oficio in _PIEZAS:
        if fragmento in n:
            return nombre, oficio
    return nombre_contenedor, ""


_MUESTRA_PREVIA: dict[str, tuple[int, int]] = {}


def _pct_cpu(clave: str, cpu_total: int, sistema_total: int, nucleos: int) -> float | None:
    previa = _MUESTRA_PREVIA.get(clave)
    _MUESTRA_PREVIA[clave] = (cpu_total, sistema_total)
    if previa is None:
        return None
    d_cpu = cpu_total - previa[0]
    d_sistema = sistema_total - previa[1]
    if d_cpu <= 0 or d_sistema <= 0:
        return 0.0
    return round((d_cpu / d_sistema) * max(nucleos, 1) * 100.0, 1)


def estadisticas(ids: list[str] | None = None, *, timeout: float = 3.0) -> list[dict[str, Any]]:
    """CPU y memoria por contenedor, al estilo `docker stats`. Nunca lanza.

    Se consultan en paralelo: son llamadas independientes al socket y en serie
    sumarían. Un contenedor que no responda sale con sus cifras en `None` en vez
    de tumbar el panel completo.
    """
    if not disponible():
        return []
    corriendo = [c for c in listar() if c.get("estado") == "running"]
    if ids:
        corriendo = [c for c in corriendo if c["id"] in ids]
    if not corriendo:
        return []

    def una(c: dict[str, Any]) -> dict[str, Any]:
        nombre_bonito, oficio = bautizar(c["nombre"])
        fila = {"id": c["id"], "nombre": c["nombre"],
                "pieza": nombre_bonito, "oficio": oficio,
                "cpu_pct": None, "mem_mb": None, "mem_pct": None,
                "mem_limite_mb": None}
        try:
            d = _get(f"/v1.44/containers/{c['id']}/stats?stream=false&one-shot=true",
                     timeout=timeout)
        except Exception:  # noqa: BLE001 — un contenedor mudo no tumba el panel
            return fila
        if not isinstance(d, dict):
            return fila
        cpu = d.get("cpu_stats") or {}
        uso = (cpu.get("cpu_usage") or {}).get("total_usage")
        sistema = cpu.get("system_cpu_usage")
        nucleos = cpu.get("online_cpus") or 1
        if isinstance(uso, int) and isinstance(sistema, int):
            fila["cpu_pct"] = _pct_cpu(c["id"], uso, sistema, nucleos)
        mem = d.get("memory_stats") or {}
        usado = mem.get("usage")
        limite = mem.get("limit")
        # Docker cuenta el caché de archivos dentro de `usage`; `docker stats` lo
        # descuenta para no reportar como "usado" lo que el kernel puede soltar.
        cache = (mem.get("stats") or {}).get("inactive_file") or 0
        if isinstance(usado, int):
            neto = max(usado - cache, 0)
            fila["mem_mb"] = round(neto / 1048576, 1)
            if isinstance(limite, int) and limite > 0:
                fila["mem_limite_mb"] = round(limite / 1048576, 1)
                fila["mem_pct"] = round(neto / limite * 100, 1)
        return fila

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(8, len(corriendo))) as pool:
        filas = list(pool.map(una, corriendo))
    # Lo que más consume, arriba: es lo que se quiere ver de un vistazo.
    filas.sort(key=lambda f: (f["cpu_pct"] or 0, f["mem_mb"] or 0), reverse=True)
    return filas


# ── Escribir por el socket: podar y reciclar ──────────────────────────────────
# Todo lo de arriba LEE. De aquí para abajo se ESCRIBE, y es lo único del repo
# que lo hace. Lo usa el botón de La Limpieza (`lib/site/limpieza.py`).
#
# Sobre el `:ro` del montaje del socket: NO es una barrera. Un socket montado en
# sólo-lectura se puede seguir usando para escribir —el flag del montaje limita
# operaciones del sistema de archivos, y conectarse a un socket no lo es—, así
# que quien tenga el socket tiene el demonio completo. Verificado el 2026-08-23
# contra un demonio real: por un socket `:ro`, crear un exec devolvió 201,
# arrancarlo 200, y el comando corrió DENTRO del contenedor objetivo. La barrera
# real es que sólo estas dos funciones escriben, y que la vista que las llama
# está gateada por permiso (o por estar en la propia máquina).


def _post(path: str, cuerpo: dict | None = None, *,
          sock: str | None = None, timeout: float = 10.0) -> Any:
    conn = _UnixHTTPConnection(sock or DOCKER_SOCK, timeout=timeout)
    try:
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        cabeceras = {"Content-Type": "application/json"} if datos else {}
        conn.request("POST", path, body=datos, headers=cabeceras)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status >= 400:
            raise RuntimeError(f"docker API {resp.status}: {body[:200]!r}")
        return json.loads(body) if body.strip()[:1] in (b"{", b"[") else None
    finally:
        conn.close()


# Qué se poda, en orden. **NUNCA `/volumes/prune`** (regla §12 del CLAUDE.md):
# ahí viven los datos. Hoy Postgres y Redis usan bind mounts (`./data/...`) y un
# prune de volúmenes no los tocaría, pero la regla se queda como está por si
# algún día se agrega un volumen nombrado — y hay una prueba que lo exige.
#
# `/images/prune` SIN filtros borra sólo las imágenes colgantes (sin etiqueta),
# que es lo que hace `docker system prune`. Con `?filters={"dangling":["false"]}`
# borraría cualquier imagen sin contenedor, y eso incluye la anterior a este
# despliegue — la que permite volver atrás si el nuevo sale mal.
_PODAS: tuple[tuple[str, str], ...] = (
    ("contenedores parados", "/v1.44/containers/prune"),
    ("imágenes colgantes", "/v1.44/images/prune"),
    ("redes huérfanas", "/v1.44/networks/prune"),
    ("caché de construcción", "/v1.44/build/prune"),
)


def podar(*, timeout: float = 8.0, presupuesto_s: float = 12.0) -> dict[str, Any]:
    """Lo que `docker system prune -f` haría, por el socket. Nunca lanza.

    `presupuesto_s` corta la poda a medias en vez de arriesgar el tiempo de
    espera de gunicorn (30 s por default): una poda incompleta no rompe nada y
    la siguiente termina el trabajo.

    El presupuesto se mide contra lo que UNA poda más podría tardar en el peor
    caso, no contra lo ya transcurrido. Si se midiera contra lo transcurrido,
    arrancar una poda justo antes del límite podría sumar un `timeout` entero por
    encima del presupuesto — y con cuatro podas eso se sale del tiempo de
    gunicorn. Es el orden lo que hace segura la poda parcial: lo que más espacio
    libera va primero, y la caché de construcción (que en este servidor está
    vacía, porque aquí no se compila) va al final.
    """
    import time as _t
    if not disponible():
        return {"disponible": False, "motivo": "no hay socket de Docker"}
    arranque = _t.monotonic()
    liberado = 0
    detalle: list[str] = []
    fallos: list[str] = []
    for etiqueta, ruta in _PODAS:
        if _t.monotonic() - arranque + timeout > presupuesto_s:
            fallos.append(f"{etiqueta}: no alcanzó el tiempo")
            continue
        try:
            d = _post(ruta, timeout=timeout) or {}
        except Exception as exc:  # noqa: BLE001 — una poda que falla no tumba el resto
            fallos.append(f"{etiqueta}: {str(exc)[:80]}")
            continue
        bytes_ = d.get("SpaceReclaimed") or 0
        liberado += bytes_
        borrados = (
            len(d.get("ContainersDeleted") or [])
            + len(d.get("ImagesDeleted") or [])
            + len(d.get("NetworksDeleted") or [])
            + len(d.get("CachesDeleted") or [])
        )
        if borrados or bytes_:
            detalle.append(f"{borrados} {etiqueta}")
    return {
        "disponible": True,
        "liberado_bytes": liberado,
        "liberado_mb": round(liberado / 1048576, 1),
        "detalle": detalle,
        "fallos": fallos,
    }


# Los contenedores a los que vale la pena reciclarles los trabajadores: los que
# corren gunicorn. El fragmento se busca en el nombre del contenedor.
#
# **El Portavoz NO va aquí, y es importante.** Comparte la imagen de La Gerencia,
# así que se parece, pero su PID 1 no es gunicorn sino `python -m
# lib.portavoz_worker`: para Python la acción por default de SIGHUP es MORIR. Un
# HUP ahí no recicla nada, mata el worker (volvería por `restart: always`, pero
# es un servicio caído sin razón). Ninguno de los fragmentos lo alcanza, y hay
# una prueba que lo fija.
_RECICLABLES: tuple[str, ...] = ("el-taller", "gerencia", "recepcion")


def reciclar_trabajadores(*, timeout: float = 4.0,
                          presupuesto_s: float = 6.0) -> dict[str, Any]:
    """Manda HUP a gunicorn en cada app, DESDE DENTRO. Nunca lanza.

    Gunicorn recibe el HUP como «recárgate»: el maestro levanta trabajadores
    nuevos y a los viejos les pide que se retiren cuando terminen lo que traen
    entre manos. Eso libera la memoria fragmentada que se acumula en el montón de
    cada proceso, y es la única parte de esta limpieza que de verdad devuelve RAM.
    No hay corte: los viejos siguen atendiendo mientras los nuevos arrancan, y el
    trabajador de gthread espera a sus peticiones en vuelo antes de irse (hasta
    `graceful_timeout`), así que la petición que disparó esto también termina.

    **NUNCA `docker kill -s HUP`.** TRAMPA PAGADA EL 2026-08-21: `docker kill`
    le cuelga al contenedor el marcador de «detenido a mano» AUNQUE el proceso
    sobreviva a la señal, y desde ese momento `restart: unless-stopped` ya no lo
    levanta tras un apagón, sin un solo error en la bitácora. Así se quedaron La
    Gerencia y El Taller abajo tras un corte de luz en el NUC. La señal va por un
    `exec` dentro del contenedor, que hace lo mismo sin que el demonio se entere.
    """
    if not disponible():
        return {"disponible": False, "motivo": "no hay socket de Docker"}
    reciclados: list[str] = []
    fallos: list[str] = []
    yo = _mi_contenedor()
    objetivos = [
        c for c in listar()
        if c.get("estado") == "running"
        and any(f in (c.get("nombre") or "").lower() for f in _RECICLABLES)
        and "portavoz" not in (c.get("nombre") or "").lower()
    ]
    # El contenedor que está atendiendo ESTA petición se recicla al final. La
    # petición sobrevive igual, pero si algo saliera mal es mejor que ya estén
    # hechos los demás.
    objetivos.sort(key=lambda c: c["id"] == yo)
    import time as _t
    arranque = _t.monotonic()
    for c in objetivos:
        nombre = bautizar(c["nombre"])[0]
        # Mismo criterio que la poda: no se arranca lo que no cabe. Aquí cada
        # contenedor son dos llamadas, así que se reserva el doble.
        if _t.monotonic() - arranque + timeout * 2 > presupuesto_s:
            fallos.append(f"{nombre}: no alcanzó el tiempo")
            continue
        try:
            d = _post(f"/v1.44/containers/{c['id']}/exec",
                      {"Cmd": ["sh", "-c", "kill -HUP 1"],
                       "AttachStdout": False, "AttachStderr": False},
                      timeout=timeout) or {}
            _post(f"/v1.44/exec/{d['Id']}/start",
                  {"Detach": True, "Tty": False}, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            fallos.append(f"{nombre}: {str(exc)[:80]}")
            continue
        reciclados.append(nombre)
    return {"disponible": True, "reciclados": reciclados, "fallos": fallos}


def _mi_contenedor() -> str:
    """El id corto del contenedor que corre este proceso, o "".

    Docker le pone al contenedor como nombre de máquina los 12 primeros
    caracteres de su id, que es justo la forma que devuelve `listar()`. Si
    alguien fijara `hostname:` en el compose esto devolvería algo que no casa con
    ningún id — y no pasa nada: sólo se usa para decidir el ORDEN del reciclado.
    """
    try:
        return socket.gethostname().strip().lower()
    except OSError:
        return ""
