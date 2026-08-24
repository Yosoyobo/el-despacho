"""Los cuatro relojes del NUC, armados una sola vez para todas las pantallas.

Antes esto vivía dentro de la vista de El Vigía, así que el Dashboard de El
Taller —que enseña los mismos cuatro relojes— tenía su propia versión, más
vieja y en inglés: «LOAD 1M», «RUNNING», la memoria en megas. Oscar lo vio de
un vistazo: «no son los mismos relojes que el vigía ni que el site».

Que se vean distintos no es un problema estético: son el mismo dato, y dos
lecturas distintas del mismo dato obligan a preguntarse cuál está bien.

Aquí queda el cálculo; cada pantalla pone su chrome. Es el mismo criterio de la
regla §4 #22, que mantiene a la par El Vigía y El Site: **comparten el origen**,
no la disciplina de acordarse.
"""

from __future__ import annotations

from typing import Any

from lib.site import gauges, host, pulso


def _num(v: Any, sufijo: str = "") -> str:
    return f"{v}{sufijo}" if v is not None else "—"


def contexto(*, con_tendencia: bool = True) -> dict:
    """Todo lo que necesitan los cuatro relojes.

    Devuelve `{infra, gauges, mem_gb, textos, trazos, presion, disponible}`.
    `con_tendencia=False` salta las series (que piden Redis) para las pantallas
    que sólo quieren el número.
    """
    infra = gauges.snapshot_gauges_minimo()
    g = infra.get("gauges") or {}
    h = infra.get("host") or {}

    ctx: dict[str, Any] = {"infra": infra, "gauges": g, "host": h}

    hay_host = bool((h.get("memoria") or {}).get("disponible")
                    or (h.get("cpu_load") or {}).get("disponible"))
    ctx["disponible"] = hay_host

    # La memoria en GIGAS, no en megas. «3933.8 MB usados» obliga a dividir
    # mentalmente para saber si son muchos o pocos; «3.8 de 15 GB» se entiende
    # de un vistazo, que es todo lo que se le pide a un tablero.
    mem = h.get("memoria") or {}
    mem_gb = {}
    if mem.get("disponible"):
        mem_gb = {
            "usado": round((mem.get("usado_mb") or 0) / 1024, 1),
            "libre": round((mem.get("libre_mb") or 0) / 1024, 1),
            "total": round((mem.get("total_mb") or 0) / 1024, 1),
        }
    ctx["mem_gb"] = mem_gb

    # El color del anillo de memoria lo decide el COLCHÓN, no el porcentaje. Un
    # 70 % de 14.8 G deja 4.4 G libres y está perfecto; un 70 % de 4 G no. Lo
    # que importa es cuánto queda, y así el anillo se pone rojo el día en que de
    # verdad hay que hacer algo, no antes.
    presion = h.get("presion") or {}
    if presion.get("disponible"):
        g = dict(g)
        m = dict(g.get("memoria") or {})
        m["color"] = {"ok": "success", "aviso": "warning",
                      "falla": "error"}.get(presion.get("estado"), "success")
        g["memoria"] = m
        ctx["gauges"] = g
        ctx["infra"] = {**infra, "gauges": g}
    ctx["presion"] = presion

    cpu = h.get("cpu_load") or {}
    disco = h.get("disco") or {}
    io = {}
    try:
        io = host.disco_io() or {}
    except Exception:  # noqa: BLE001 — sin /proc no hay tasas, y no pasa nada
        io = {}
    ctx["io"] = io

    ctx["textos"] = {
        "cpu_a": _num(cpu.get("cores"), " núcleos activos"),
        "cpu_b": f"5 min: {cpu.get('load_5')}" if cpu.get("load_5") is not None else "",
        "mem_unidad": f"de {mem_gb.get('total')} GB" if mem_gb.get("total") else "GB",
        "mem_a": (presion.get("detalle") if presion.get("estado") not in (None, "ok")
                  else _num(mem_gb.get("libre"), " GB libres")),
        "disco_unidad": (f"de {disco.get('total_gb')} GB"
                         if disco.get("total_gb") is not None else "GB"),
        "disco_a": _num(disco.get("libre_gb"), " GB libres"),
        "disco_b": (f"{io.get('lectura_mb_s')} lee · {io.get('escritura_mb_s')} escribe MB/s"
                    if io.get("disponible") else ""),
    }

    ctx["trazos"] = {}
    if con_tendencia:
        try:
            series = pulso.leer_varias(["cpu", "mem", "disco_lee", "disco_escribe"])
            # `relieve=True` en CPU y memoria porque son las que se mueven POCO
            # y en rangos estrechos: con el eje de 0 a 100, una memoria entre
            # 25.4 % y 25.9 % sale como una raya y parece que no pasa nada.
            ctx["trazos"] = {
                "cpu": pulso.area(series["cpu"], relieve=True),
                "mem": pulso.area(series["mem"], relieve=True),
                "disco_lee": pulso.area(series["disco_lee"]),
                "disco_escribe": pulso.area(series["disco_escribe"]),
            }
        except Exception:  # noqa: BLE001 — la tendencia es un extra, no el dato
            ctx["trazos"] = {}

    resumen = infra.get("containers_resumen") or {}
    ctx["containers_resumen"] = resumen
    corriendo = resumen.get("running") or 0
    parados = resumen.get("stopped") or 0
    ctx["piezas"] = {
        "corriendo": corriendo,
        "total": corriendo + parados,
        # «Todas» se lee mejor que «0 abajo», y decir cuántas faltan sólo tiene
        # sentido cuando falta alguna.
        "resumen": "Todas" if not parados else f"{parados} abajo",
    }
    return ctx


__all__ = ["contexto"]
