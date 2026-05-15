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
        "uptime": uptime(),
    }
