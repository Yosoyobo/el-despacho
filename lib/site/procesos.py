"""Qué está consumiendo la máquina, proceso por proceso.

Los relojes de arriba dicen **cuánto** se está usando; esto dice **quién**.
Cuando el CPU sube al 80 % o la memoria se estrecha, la pregunta útil no es el
porcentaje sino qué proceso lo está pidiendo: un reporte pesado, el
preprocesado de un mapa, un Chromium armando un PDF o algo que se desbocó.

Se lee de `/proc`, que ya viene montado de sólo lectura (`SITE_PROC_ROOT`).
No hace falta instalar nada ni abrir ningún puerto.

**El CPU necesita dos muestras.** Un proceso guarda cuánto tiempo de CPU lleva
consumido *en total* desde que nació, no un porcentaje: el porcentaje es la
diferencia entre dos lecturas dividida entre el tiempo transcurrido. Por eso se
guarda la muestra anterior en el proceso — el mismo truco que ya usa
`contenedores.estadisticas`, y por el mismo motivo. **La primera lectura tras
arrancar muestra el CPU en blanco; de la segunda en adelante, real.**

Nada aquí lanza: si `/proc` no está (macOS, pruebas), se devuelve
`disponible=False` y quien llama pinta un «no se puede medir desde aquí».
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROC_ROOT = Path(os.environ.get("SITE_PROC_ROOT", "/host/proc"))

#: Ticks de reloj por segundo. Es 100 en prácticamente todo Linux; se deja como
#: constante para no depender de `os.sysconf` dentro del contenedor.
TICKS_POR_SEGUNDO = 100

#: Cuántos procesos se devuelven. Más que esto es ruido en una pared.
TOPE = 8

#: Muestra anterior: {pid: (tiempo_cpu_en_ticks, arranque)}. Se guarda para
#: poder calcular el porcentaje contra la lectura siguiente.
_anterior: tuple[float, dict[int, tuple[int, int]]] | None = None


def disponible() -> bool:
    return PROC_ROOT.exists()


def _leer(p: Path) -> str | None:
    try:
        return p.read_text(errors="replace")
    except (OSError, PermissionError):
        return None


def _nombre(pid: int) -> str:
    """El comando tal como se invocó, recortado.

    Se prefiere `cmdline` sobre `comm` porque `comm` dice «python3» para todo
    y no distingue El Taller de un cron. Si `cmdline` está vacío (procesos del
    kernel), se cae a `comm`.
    """
    crudo = _leer(PROC_ROOT / str(pid) / "cmdline")
    if crudo:
        partes = [x for x in crudo.split("\0") if x]
        if partes:
            texto = " ".join(partes)
            # Las rutas largas no dicen nada: «/usr/local/bin/gunicorn» es
            # sólo «gunicorn» para quien está mirando el tablero.
            texto = " ".join(x.rsplit("/", 1)[-1] if x.startswith("/") else x
                             for x in texto.split(" "))
            return texto[:70]
    comm = _leer(PROC_ROOT / str(pid) / "comm")
    return (comm or "?").strip()[:70]


def _stat(pid: int) -> tuple[int, int, int] | None:
    """(tiempo de CPU en ticks, memoria residente en páginas, arranque).

    El nombre del proceso va entre paréntesis y **puede contener espacios y
    paréntesis**, así que el campo se corta desde el ÚLTIMO `)` — partir por
    espacios daría columnas corridas en cualquier proceso con un espacio en su
    nombre.
    """
    txt = _leer(PROC_ROOT / str(pid) / "stat")
    if not txt:
        return None
    try:
        resto = txt[txt.rindex(")") + 2:].split()
        utime, stime = int(resto[11]), int(resto[12])
        arranque = int(resto[19])
        rss_paginas = int(resto[21])
        return utime + stime, rss_paginas, arranque
    except (ValueError, IndexError):
        return None


def top(n: int = TOPE) -> dict[str, Any]:
    """Los procesos que más CPU están pidiendo, con su memoria.

    Devuelve `{disponible, procesos, primera_lectura}`. `primera_lectura` avisa
    que el CPU todavía no se puede calcular porque no hay con qué comparar.
    """
    global _anterior

    if not disponible():
        return {"disponible": False, "procesos": [], "primera_lectura": False}

    ahora = time.monotonic()
    actual: dict[int, tuple[int, int]] = {}
    crudos: list[dict[str, Any]] = []
    pagina = 4096  # tamaño de página en todo x86_64

    try:
        pids = [int(d.name) for d in PROC_ROOT.iterdir() if d.name.isdigit()]
    except OSError as exc:
        logger.debug("procesos: no se pudo listar /proc: %s", exc)
        return {"disponible": False, "procesos": [], "primera_lectura": False}

    for pid in pids:
        datos = _stat(pid)
        if datos is None:
            continue  # el proceso murió entre listar y leer: normal
        ticks, rss_paginas, arranque = datos
        actual[pid] = (ticks, arranque)
        crudos.append({
            "pid": pid,
            "ticks": ticks,
            "arranque": arranque,
            "memoria_mb": round(rss_paginas * pagina / (1024 * 1024), 1),
        })

    previa = _anterior
    _anterior = (ahora, actual)

    primera = previa is None
    transcurrido = (ahora - previa[0]) if previa else 0.0

    for p in crudos:
        p["cpu"] = None
        if previa and transcurrido > 0:
            antes = previa[1].get(p["pid"])
            # Si el arranque cambió, el PID se reusó para OTRO proceso: comparar
            # los dos daría un porcentaje disparatado.
            if antes and antes[1] == p["arranque"]:
                delta = p["ticks"] - antes[0]
                if delta >= 0:
                    p["cpu"] = round((delta / TICKS_POR_SEGUNDO) / transcurrido * 100, 1)

    # Por CPU cuando se puede; por memoria en la primera lectura, que es la
    # única señal disponible todavía.
    clave = (lambda p: (p["cpu"] or 0, p["memoria_mb"])) if not primera else (
        lambda p: p["memoria_mb"])
    crudos.sort(key=clave, reverse=True)

    procesos = []
    for p in crudos[:n]:
        procesos.append({
            "pid": p["pid"],
            "nombre": _nombre(p["pid"]),
            "cpu": p["cpu"],
            "memoria_mb": p["memoria_mb"],
        })

    return {"disponible": True, "procesos": procesos, "primera_lectura": primera}


def olvidar_muestra() -> None:
    """Tira la muestra anterior. Para pruebas."""
    global _anterior
    _anterior = None


__all__ = ["PROC_ROOT", "TOPE", "disponible", "olvidar_muestra", "top"]
