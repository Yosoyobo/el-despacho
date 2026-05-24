"""S-LC-Feedback-V5 c8 — helpers para aplicar metas a KPI hero cards.

Uso típico desde una view:

    from apps.taller_home.services_meta_kpi import enriquecer_con_meta
    kpi_card_ctx = enriquecer_con_meta(kpi_card_ctx, "ingresos-mes")
    # Ahora kpi_card_ctx tiene: meta_valor, meta_porcentaje, meta_porcentaje_clamp
"""

from __future__ import annotations

from decimal import Decimal


def obtener_meta(kpi_slug: str):
    try:
        from apps.taller_home.models.meta_kpi import MetaKPI
        return MetaKPI.objects.filter(kpi_slug=kpi_slug, activa=True).first()
    except Exception:
        return None


def enriquecer_con_meta(ctx: dict, kpi_slug: str, *, valor_numerico=None) -> dict:
    """Añade meta_valor/meta_porcentaje/meta_porcentaje_clamp al ctx si hay meta.

    `valor_numerico`: el valor crudo del KPI (Decimal/int/float). Si no se
    pasa, intenta parsear desde ctx["valor"] (str). Si no se puede parsear,
    no añade meta.
    """
    meta = obtener_meta(kpi_slug)
    if meta is None:
        return ctx
    if valor_numerico is None:
        valor_numerico = ctx.get("valor")
        if isinstance(valor_numerico, str):
            try:
                v = valor_numerico.replace("$", "").replace(",", "").strip()
                valor_numerico = float(v) if v else None
            except (ValueError, TypeError):
                valor_numerico = None
    if valor_numerico is None:
        return ctx
    meta_v = float(meta.valor)
    if meta_v <= 0:
        return ctx
    pct = (float(valor_numerico) / meta_v) * 100.0
    ctx["meta_valor"] = f"${meta_v:,.0f}" if meta_v >= 100 else f"{meta_v}"
    ctx["meta_porcentaje"] = round(pct, 1)
    ctx["meta_porcentaje_clamp"] = min(max(round(pct), 0), 100)
    return ctx


def listar_metas_aplicables() -> dict:
    """Retorna `{kpi_slug: MetaKPI}` para todas las metas activas."""
    try:
        from apps.taller_home.models.meta_kpi import MetaKPI
        return {m.kpi_slug: m for m in MetaKPI.objects.filter(activa=True)}
    except Exception:
        return {}
