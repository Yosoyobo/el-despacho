"""Compatibilidad: las metas de KPI para pantallas que no son el Inicio.

Desde S-KPIs-V2 la lógica vive en `metas.py` (proporcional al periodo, con
dirección, por persona y cliente). Esto la envuelve para quien ya la llamaba
(La Tesorería):

    ctx = enriquecer_con_meta({"valor": "$12,000"}, "ingresos-mes", valor_numerico=12000)
    # ctx["meta"] → dict listo para `_kpi_card_hero.html` (param `meta`)
    # ctx["meta_valor"/"meta_porcentaje"/"meta_porcentaje_clamp"] → forma vieja
"""

from __future__ import annotations


def obtener_meta(kpi_slug: str):
    """La meta del DESPACHO activa de ese KPI (o None)."""
    try:
        from apps.taller_home.models.meta_kpi import MetaKPI
        return MetaKPI.objects.filter(kpi_slug=kpi_slug, activa=True, ambito="despacho").first()
    except Exception:  # noqa: BLE001
        return None


def enriquecer_con_meta(ctx: dict, kpi_slug: str, *, valor_numerico=None, user=None) -> dict:
    """Añade la meta del despacho de `kpi_slug`, ya evaluada, al contexto."""
    from .kpi_valor import numero_de
    from .kpis import kpi_por_slug
    from .metas import meta_para_tarjeta
    from .tablero import configs, efectivo

    kpi = kpi_por_slug(kpi_slug)
    meta = obtener_meta(kpi_slug)
    if kpi is None or meta is None:
        return ctx
    numero = numero_de(valor_numerico if valor_numerico is not None else ctx.get("valor"))
    evaluada = meta_para_tarjeta(user, efectivo(kpi, configs()), numero, metas=[meta])
    if not evaluada:
        return ctx
    ctx["meta"] = evaluada
    ctx["meta_valor"] = evaluada["meta_txt"]
    ctx["meta_porcentaje"] = evaluada["avance_pct"]
    ctx["meta_porcentaje_clamp"] = evaluada["avance_clamp"]
    return ctx


def listar_metas_aplicables() -> dict:
    """`{kpi_slug: MetaKPI}` de las metas del despacho activas."""
    try:
        from apps.taller_home.models.meta_kpi import MetaKPI
        return {m.kpi_slug: m for m in MetaKPI.objects.filter(activa=True, ambito="despacho")}
    except Exception:  # noqa: BLE001
        return {}
