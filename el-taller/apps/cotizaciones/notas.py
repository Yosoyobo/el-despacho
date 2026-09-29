"""Notas al pie de la cotización.

Hasta 2026-09-29 eran fijas en código (decisión de Oscar de julio: «las notas van
siempre, tal cual»). Desde La Imprenta **se editan en La Gerencia** (Ajustes →
Documentos → Cotización → Notas; permiso `documentos.editar_notas`) y cada
cotización puede **quitar** alguna o **sumar** las suyas (`notas_omitidas`,
`notas_extra`). Las de fábrica siguen siendo las de siempre, así que nada cambia
hasta que alguien las edite.

La última sigue siendo automática: la forma de pago, que depende del interruptor
Anticipo / Un solo pago de la cotización.
"""

from __future__ import annotations

from imprenta.tipos import NOTAS_COTIZACION as NOTAS_FIJAS


def notas_globales(cfg=None) -> list[dict]:
    """Las notas de La Gerencia: `[{id, texto, activa}]`, en su orden."""
    if cfg is None:
        from imprenta.config import resolver

        cfg = resolver("cotizacion")
    return list(cfg.doc.get("notas") or [])


def notas_para(cotizacion, cfg=None) -> list[str]:
    """Las notas del documento, en orden. La última es la forma de pago.

    Globales activas, menos las que esta cotización quitó, más las suyas.
    """
    if cfg is None:
        from imprenta.config import resolver

        cfg = resolver("cotizacion")
    omitidas = set(getattr(cotizacion, "notas_omitidas", None) or [])
    notas = [n["texto"] for n in notas_globales(cfg)
             if n.get("activa", True) and n.get("id") not in omitidas]
    extra = getattr(cotizacion, "notas_extra", "") or ""
    notas += [" ".join(r.split()) for r in extra.splitlines() if r.strip()]
    if cfg.doc.get("nota_automatica", True):
        notas.append(cotizacion.nota_forma_pago)
    return notas


def notas_de_la_cotizacion(cotizacion, cfg=None) -> list[dict]:
    """Para el recuadro «Documento»: cada nota global activa y si va en ésta."""
    omitidas = set(getattr(cotizacion, "notas_omitidas", None) or [])
    return [{"id": n["id"], "texto": n["texto"], "incluida": n["id"] not in omitidas}
            for n in notas_globales(cfg) if n.get("activa", True)]


__all__ = ["NOTAS_FIJAS", "notas_de_la_cotizacion", "notas_globales", "notas_para"]
