"""El tablero de KPIs de cada persona y la tarjeta de cada KPI (S-KPIs-V2).

Decisión de Oscar (2026-09-29): «Gerencia arma, cada quien ajusta».

1. **La base** es el tablero de los roles de la persona (`TableroKPI`), en el
   orden que se decidió en La Gerencia. Si ninguno de sus roles tiene tablero,
   el por omisión (`rol=None`).
2. **Encima**, lo que la persona cambió en Perfil → Tablero (`PreferenciaKPI`):
   `visible=False` lo quita; `visible=True` sobre algo que no estaba en su
   base lo agrega; `orden` lo acomoda.
3. **Siempre** dentro de lo que su permiso le deja ver, y sin los KPIs que La
   Gerencia apagó (`ConfigKPI.activo=False`).

Hasta hoy el Inicio pintaba 8 KPIs fijos en el código y la página de
preferencias ofrecía ~90: marcar cualquier otro no cambiaba nada.
"""

from __future__ import annotations

import json
from dataclasses import replace

# ── La configuración de La Gerencia ──────────────────────────────────────


def configs() -> dict:
    """`{slug: ConfigKPI}` — tabla chica, una consulta."""
    from .models import ConfigKPI

    try:
        return {c.kpi_slug: c for c in ConfigKPI.objects.all()}
    except Exception:  # noqa: BLE001 — sin la tabla (migrando) todo es default
        return {}


def apagados(cfgs: dict | None = None) -> set[str]:
    cfgs = configs() if cfgs is None else cfgs
    return {slug for slug, c in cfgs.items() if not c.activo}


def efectivo(kpi, cfgs: dict):
    """El KPI con la dirección que haya elegido La Gerencia (si eligió)."""
    cfg = cfgs.get(kpi.slug)
    if cfg and cfg.direccion and cfg.direccion != kpi.direccion:
        return replace(kpi, direccion=cfg.direccion)
    return kpi


def semaforo(kpi, numero: float | None, cfg) -> str:
    """`rojo` · `amarillo` · `verde` según los umbrales de La Gerencia, o `""`.

    Con «sube», los umbrales son pisos (por debajo se pinta); con «baja»,
    techos (por encima). Un umbral vacío no juzga (vacío no es cero)."""
    if cfg is None or numero is None:
        return ""
    direccion = cfg.direccion or kpi.direccion
    if direccion == "neutro":
        return ""
    rojo = float(cfg.umbral_rojo) if cfg.umbral_rojo is not None else None
    amarillo = float(cfg.umbral_amarillo) if cfg.umbral_amarillo is not None else None
    if rojo is None and amarillo is None:
        return ""
    if direccion == "baja":
        if rojo is not None and numero >= rojo:
            return "rojo"
        if amarillo is not None and numero >= amarillo:
            return "amarillo"
    else:
        if rojo is not None and numero <= rojo:
            return "rojo"
        if amarillo is not None and numero <= amarillo:
            return "amarillo"
    return "verde"


# ── El tablero ───────────────────────────────────────────────────────────


def _roles_de(user):
    """Los roles cuyo tablero cuenta para `user` (respeta «ver como rol»)."""
    from cuentas.models.rol import Rol

    sim = getattr(user, "_rol_simulado", None)
    if sim:
        return list(Rol.objects.filter(clave=sim))
    try:
        return list(user.roles_extra.all())
    except Exception:  # noqa: BLE001
        return []


def base_de(user) -> list[str]:
    """Los slugs del tablero base de `user`, en orden (roles, o el por omisión)."""
    from .models import TableroKPI

    roles = _roles_de(user)
    filas = []
    if roles:
        filas = list(
            TableroKPI.objects.filter(rol__in=roles)
            .select_related("rol").order_by("rol__nombre", "orden", "pk")
        )
    if not filas:
        filas = list(TableroKPI.objects.filter(rol__isnull=True).order_by("orden", "pk"))
    vistos: set[str] = set()
    salida = []
    for f in filas:
        if f.kpi_slug not in vistos:
            vistos.add(f.kpi_slug)
            salida.append(f.kpi_slug)
    return salida


def base_de_rol(rol) -> list[str]:
    """El tablero de un rol tal como está guardado (`rol=None`: por omisión)."""
    from .models import TableroKPI

    qs = TableroKPI.objects.filter(rol=rol) if rol else TableroKPI.objects.filter(rol__isnull=True)
    return list(qs.order_by("orden", "pk").values_list("kpi_slug", flat=True))


def kpis_del_tablero(user) -> list:
    """Los KPIs (objetos `KPI`) del tablero de `user`, ya en su orden.

    Base de sus roles − lo que ocultó + lo que agregó + sus KPIs del Chalán,
    filtrado por permiso y por lo que La Gerencia dejó prendido."""
    from .kpis import kpis_aplicables
    from .models import PreferenciaKPI

    aplicables = {k.slug: k for k in kpis_aplicables(user)}
    base = base_de(user)
    prefs = {
        p.kpi_slug: p
        for p in PreferenciaKPI.objects.filter(usuario=user).exclude(kpi_slug__startswith="hero-")
    }
    elegidos: list[str] = []
    for slug in base:
        p = prefs.get(slug)
        if p is not None and not p.visible:
            continue
        elegidos.append(slug)
    for slug, p in prefs.items():
        if p.visible and slug not in elegidos:
            elegidos.append(slug)
    # Los KPIs que la persona le pidió a El Chalán siempre entran (se ocultan
    # como cualquier otro).
    for slug in aplicables:
        if slug.startswith("custom-") and slug not in elegidos:
            p = prefs.get(slug)
            if p is None or p.visible:
                elegidos.append(slug)

    posicion = {slug: i for i, slug in enumerate(elegidos)}

    def _orden(slug: str):
        p = prefs.get(slug)
        if p is not None and p.orden is not None:
            return (0, p.orden, posicion[slug])
        return (1, posicion[slug], 0)

    return [aplicables[s] for s in sorted(elegidos, key=_orden) if s in aplicables]


def en_base(user) -> set[str]:
    return set(base_de(user))


# ── La tarjeta ───────────────────────────────────────────────────────────


def tarjeta(user, kpi, resultado: dict, *, cfgs: dict, metas: list | None = None,
            sparkline: list | None = None) -> dict:
    """Todo lo que la tarjeta de un KPI necesita para pintarse."""
    from .kpi_valor import formatear, numero_del_resultado
    from .metas import meta_para_tarjeta

    kpi = efectivo(kpi, cfgs)
    numero = numero_del_resultado(resultado)
    valor = resultado.get("valor", "—")
    if not isinstance(valor, str) and numero is not None:
        valor = formatear(numero, kpi.formato)
    nota = resultado.get("nota", "") or ""
    color = semaforo(kpi, numero, cfgs.get(kpi.slug))
    meta = meta_para_tarjeta(user, kpi, numero, metas=metas, direccion=kpi.direccion)
    item = {
        "slug": kpi.slug,
        "titulo": kpi.titulo,
        "descripcion": kpi.descripcion,
        "valor": valor,
        "numero": numero,
        "nota": "" if nota == "alerta" else nota,
        "alerta": color == "rojo" or (not color and nota == "alerta"),
        "semaforo": color,
        "link": resultado.get("link", "") or "",
        "formato": kpi.formato,
        "sparkline_formato": "moneda" if kpi.formato == "dinero" else "",
        "meta": meta,
    }
    if sparkline and len(sparkline) >= 2:
        item["sparkline_serie"] = json.dumps(sparkline)
    return item
