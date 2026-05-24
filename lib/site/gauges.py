"""Helpers compartidos para renderear gauges SVG del droplet.

Origen: la-gerencia/apps/el_site/views.py (S2a). Extraído en
S-Demo-Pre-Showcase para que el Dashboard del Taller pueda reusarlos
sin tener que importar de la app `el_site` (que sólo vive en
la-gerencia).

Requiere que el container tenga /proc, docker.sock y caddy data
montados como en docker-compose.site.yml.
"""

from __future__ import annotations

from . import caddy, contenedores, droplet, host, postgres, redis_status


def gauge(pct: float | None, *, umbral_warn: float = 60, umbral_err: float = 80) -> dict:
    """Pre-calcula coordenadas de un arco SVG (270°) para un gauge radial.

    Devuelve `{disponible, pct, color, stroke_dasharray, stroke_dasharray_track,
    radio}`. Si pct es None, retorna `{disponible: False}` y el template
    pinta placeholder.
    """
    if pct is None:
        return {"disponible": False}
    pct_c = max(0.0, min(100.0, float(pct)))
    if pct_c >= umbral_err:
        color = "error"
    elif pct_c >= umbral_warn:
        color = "warning"
    else:
        color = "success"
    radio = 42
    circ = 2 * 3.14159265 * radio
    arco_total = circ * 0.75  # 270°
    relleno = arco_total * (pct_c / 100)
    return {
        "disponible": True,
        "pct": round(pct_c, 1),
        "color": color,
        "stroke_dasharray": f"{relleno:.2f} {circ:.2f}",
        "stroke_dasharray_track": f"{arco_total:.2f} {circ:.2f}",
        "radio": radio,
    }


def snapshot_infra() -> dict:
    """Snapshot completo de infraestructura. Mismo formato que `_ctx_infra`
    de el_site/views.py (mantener sincronizado)."""
    h = host.snapshot()
    c = contenedores.snapshot()
    cd = caddy.snapshot()

    mem_pct = h["memoria"].get("pct_usado") if h["memoria"].get("disponible") else None
    dis_pct = h["disco"].get("pct_usado") if h["disco"].get("disponible") else None
    cpu = h["cpu_load"]
    load_pct = None
    if cpu.get("disponible") and cpu.get("cores"):
        load_pct = (cpu["load_1"] / max(cpu["cores"], 1)) * 100

    info_c = c.get("info", {}) if isinstance(c, dict) else {}
    running = info_c.get("running", 0) if info_c.get("disponible") else 0
    stopped = info_c.get("stopped", 0) if info_c.get("disponible") else 0
    total_c = max(running + stopped, 1)
    pct_running = (running / total_c) * 100 if info_c.get("disponible") else None

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
            "cpu": gauge(load_pct, umbral_warn=70, umbral_err=100),
            "memoria": gauge(mem_pct),
            "disco": gauge(dis_pct, umbral_warn=75, umbral_err=85),
            "containers_running": gauge(pct_running, umbral_warn=0, umbral_err=0)
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


def snapshot_gauges_minimo() -> dict:
    """Versión reducida — sólo lo que necesita el Dashboard del Taller:
    los 4 gauges + datos básicos del host. Evita pegar a Postgres/Caddy
    cuando no se va a renderear.

    Pensado para llamar en cada render del home del Taller — no acumula
    estado, no requiere DB.
    """
    h = host.snapshot()
    c = contenedores.snapshot()

    mem_pct = h["memoria"].get("pct_usado") if h["memoria"].get("disponible") else None
    dis_pct = h["disco"].get("pct_usado") if h["disco"].get("disponible") else None
    cpu = h["cpu_load"]
    load_pct = None
    if cpu.get("disponible") and cpu.get("cores"):
        load_pct = (cpu["load_1"] / max(cpu["cores"], 1)) * 100

    info_c = c.get("info", {}) if isinstance(c, dict) else {}
    running = info_c.get("running", 0) if info_c.get("disponible") else 0
    stopped = info_c.get("stopped", 0) if info_c.get("disponible") else 0
    total_c = max(running + stopped, 1)
    pct_running = (running / total_c) * 100 if info_c.get("disponible") else None

    return {
        "host": h,
        "containers": c,
        "gauges": {
            "cpu": gauge(load_pct, umbral_warn=70, umbral_err=100),
            "memoria": gauge(mem_pct),
            "disco": gauge(dis_pct, umbral_warn=75, umbral_err=85),
            "containers_running": gauge(pct_running, umbral_warn=0, umbral_err=0)
            if info_c.get("disponible") else {"disponible": False},
        },
        "containers_resumen": {
            "running": running,
            "stopped": stopped,
            "total": running + stopped,
            "pct_running": round(pct_running, 1) if pct_running is not None else None,
        },
    }
