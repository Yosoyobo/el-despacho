"""Lectura del host (CPU, memoria, disco, load). Lee /proc y /sys; en macOS
o en tests sin /proc, retorna estructuras con `disponible=False`.

En producción el container de La Gerencia monta /proc y /sys como ro desde
el host (ver docker-compose.prod.yml).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

PROC_ROOT = Path(os.environ.get("SITE_PROC_ROOT", "/host/proc"))
SYS_ROOT = Path(os.environ.get("SITE_SYS_ROOT", "/host/sys"))
DISCO_ROOT = Path(os.environ.get("SITE_DISCO_ROOT", "/host"))


def _leer(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def cpu_y_load() -> dict[str, Any]:
    loadavg = _leer(PROC_ROOT / "loadavg")
    cpuinfo = _leer(PROC_ROOT / "cpuinfo")
    if loadavg is None:
        return {"disponible": False}
    partes = loadavg.split()
    cores = cpuinfo.count("processor\t:") if cpuinfo else None
    return {
        "disponible": True,
        "load_1": float(partes[0]),
        "load_5": float(partes[1]),
        "load_15": float(partes[2]),
        "cores": cores,
    }


def memoria() -> dict[str, Any]:
    txt = _leer(PROC_ROOT / "meminfo")
    if txt is None:
        return {"disponible": False}
    vals: dict[str, int] = {}
    for linea in txt.splitlines():
        if ":" not in linea:
            continue
        k, _, v = linea.partition(":")
        v = v.strip().split()
        if v and v[0].isdigit():
            vals[k.strip()] = int(v[0])  # kB
    total = vals.get("MemTotal", 0)
    libre = vals.get("MemAvailable", vals.get("MemFree", 0))
    usado = total - libre
    pct = (usado / total * 100) if total else 0.0
    return {
        "disponible": True,
        "total_mb": round(total / 1024, 1),
        "usado_mb": round(usado / 1024, 1),
        "libre_mb": round(libre / 1024, 1),
        "pct_usado": round(pct, 1),
    }


# El colchón de memoria que NO se toca, en gigas. Decisión de Oscar (2026-08-22):
# el NUC tiene 14.8 G, se reparten ~10.8 y estos 4 se quedan libres siempre.
#
# Existe como constante y no como número suelto porque de aquí salen dos cosas: el
# color del anillo de memoria en El Vigía y el módulo de `/salud`. La idea es que
# **nadie tenga que volver a un servidor headless a adivinar si le falta memoria**:
# si el colchón se rompe, el sistema lo dice solo, en la pared y en el monitor.
COLCHON_GB = float(os.environ.get("NUC_COLCHON_GB", "4"))


def presion_memoria() -> dict[str, Any]:
    """¿Queda el colchón de memoria acordado? Nunca lanza.

    Devuelve `estado` en tres pasos, no dos, porque «ok» y «falla» no alcanzan:
    hace falta el escalón intermedio que avisa ANTES de que duela, que es el
    único momento en que sirve enterarse.

      ok       queda más del colchón completo
      aviso    queda entre el colchón y la mitad — es hora de mirar
      falla    queda menos de la mitad del colchón — hay que actuar
    """
    m = memoria()
    if not m.get("disponible"):
        return {"disponible": False}
    libre_gb = (m.get("libre_mb") or 0) / 1024
    if libre_gb >= COLCHON_GB:
        estado = "ok"
    elif libre_gb >= COLCHON_GB / 2:
        estado = "aviso"
    else:
        estado = "falla"
    return {
        "disponible": True,
        "estado": estado,
        "libre_gb": round(libre_gb, 1),
        "colchon_gb": COLCHON_GB,
        "detalle": (f"quedan {libre_gb:.1f} G libres de un colchón de "
                    f"{COLCHON_GB:.0f} G"),
    }


def disco(path: str | Path | None = None) -> dict[str, Any]:
    """Espacio en disco del path raíz montado. En el container con
    /host:ro, usa `SITE_DISCO_ROOT=/host`. Si no existe, cae a `/`."""
    p = Path(path) if path else DISCO_ROOT
    if not p.exists():
        p = Path("/")
    try:
        u = shutil.disk_usage(p)
    except OSError:
        return {"disponible": False}
    pct = (u.used / u.total * 100) if u.total else 0.0
    return {
        "disponible": True,
        "path": str(p),
        "total_gb": round(u.total / (1024**3), 2),
        "usado_gb": round(u.used / (1024**3), 2),
        "libre_gb": round(u.free / (1024**3), 2),
        "pct_usado": round(pct, 1),
    }


# La muestra anterior de `/proc/diskstats`, por dispositivo. `diskstats` da
# contadores ACUMULADOS desde el arranque, así que un solo vistazo no dice nada:
# lo que importa es cuánto crecieron entre dos lecturas.
_IO_PREVIO: dict[str, tuple[float, int, int]] = {}

# Los dispositivos que NO son discos de verdad: `loop*` son los paquetes snap
# montados (en este NUC hay una docena) y `ram*`/`zram*` son memoria. Si se
# contaran, la cifra de lectura saldría inflada por cosas que no tocan el SSD.
_NO_ES_DISCO = ("loop", "ram", "zram", "dm-", "sr")


def sumar_sectores(diskstats: str) -> tuple[int, int]:
    """Los sectores leídos y escritos de los discos DE VERDAD, sumados.

    Separado de `disco_io` para poderse probar: la tasa depende del tiempo entre
    dos lecturas, así que un test que compare tasas compara relojes. Lo que hay
    que fijar es qué dispositivos cuentan y qué columnas se leen.
    """
    leidos = escritos = 0
    for linea in diskstats.splitlines():
        campos = linea.split()
        if len(campos) < 10:
            continue
        nombre = campos[2]
        if nombre.startswith(_NO_ES_DISCO):
            continue
        # Sólo el disco entero, no sus particiones: `sda` sí, `sda1` no. Contando
        # las dos, cada byte se contaría doble. En NVMe la forma es al revés —el
        # disco es `nvme0n1` y la partición `nvme0n1p1`— así que ahí lo que
        # descarta es la `p`.
        if "p" in nombre[4:] if nombre.startswith("nvme") else nombre[-1].isdigit():
            continue
        try:
            leidos += int(campos[5])    # sectores leídos
            escritos += int(campos[9])  # sectores escritos
        except ValueError:
            continue
    return leidos, escritos


def disco_io() -> dict[str, Any]:
    """Lectura y escritura del disco, en MB/s. Nunca lanza.

    Se mide porque el disco OCUPADO no se mueve —14.5% hoy, 14.5% mañana— y en
    una pared una línea plana no dice nada. Lo que sí se mueve, y sí interesa, es
    cuánto está trabajando el disco.

    La primera llamada devuelve `disponible=False`: hacen falta dos muestras para
    tener una tasa, y devolver cero ahí sería mentir con «el disco está quieto».
    """
    txt = _leer(PROC_ROOT / "diskstats")
    if txt is None:
        return {"disponible": False}
    import time as _t
    ahora = _t.monotonic()
    leidos, escritos = sumar_sectores(txt)

    previo = _IO_PREVIO.get("total")
    _IO_PREVIO["total"] = (ahora, leidos, escritos)
    if not previo:
        return {"disponible": False, "motivo": "primera muestra"}
    t0, l0, e0 = previo
    segundos = ahora - t0
    if segundos <= 0:
        return {"disponible": False}
    # Un sector son 512 bytes, por convención del kernel.
    mb = 512 / 1048576
    return {
        "disponible": True,
        "lectura_mb_s": round(max(leidos - l0, 0) * mb / segundos, 2),
        "escritura_mb_s": round(max(escritos - e0, 0) * mb / segundos, 2),
    }


def uptime() -> dict[str, Any]:
    txt = _leer(PROC_ROOT / "uptime")
    if txt is None:
        return {"disponible": False}
    seg = float(txt.split()[0])
    dias = int(seg // 86400)
    horas = int((seg % 86400) // 3600)
    return {"disponible": True, "segundos": int(seg), "humano": f"{dias}d {horas}h"}


def snapshot() -> dict[str, Any]:
    return {
        "cpu_load": cpu_y_load(),
        "memoria": memoria(),
        "disco": disco(),
        "disco_io": disco_io(),
        "presion": presion_memoria(),
        "uptime": uptime(),
    }
