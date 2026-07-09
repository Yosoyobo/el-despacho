"""Motor fiscal compartido — desgloses de impuestos (IVA / retenciones).

Vive en `lib/` (no-Django, importable desde cualquier app) para que Facturación,
Cotizaciones y Proyectos usen EXACTAMENTE la misma lógica y cuadren al centavo.

Dos regímenes de documento (campo `regimen_fiscal` en Factura/Cotización/Proyecto):

- ``iva``       — solo IVA trasladado (mecanismo genérico de `TasaImpositiva`
                  vía la M2M del documento). Comportamiento histórico.
- ``honorarios``— RESICO / Actividad Profesional (honorarios): IVA trasladado +
                  Retención de ISR + Retención de IVA (⅔ del IVA). Las tasas y la
                  fracción de la retención de IVA viven en `ConfiguracionFiscal`
                  (GUI de Gerencia). Cálculo dedicado y exacto (no cabe como
                  porcentaje de 2 decimales sobre la base).
- ``exento``    — sin impuestos.

**Redondeo:** convención fiscal/contable mexicana = ROUND_HALF_UP (no el
HALF_EVEN por defecto de Python). Caso de auditoría (LC 2026-07):

    Importe          33,770.00
    + IVA 16%         5,403.20
    - Ret. ISR 1.25%    422.13   (33,770 × 1.25% = 422.125 → HALF_UP → 422.13)
    - Ret. IVA ⅔        3,602.13   (⅔ × 5,403.20 = 3,602.1333… → 3,602.13)
    = Total neto     35,148.94
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
CIEN = Decimal("100")

# Choices del régimen fiscal a nivel documento/proyecto. Fuente única.
REGIMENES_FISCALES = (
    ("iva", "IVA (16%)"),
    ("honorarios", "IVA y Retenciones"),
    ("exento", "Exento"),
)


def q2(x) -> Decimal:
    """Cuantiza a centavos con ROUND_HALF_UP (convención fiscal MX)."""
    if x is None:
        return Decimal("0.00")
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def _config():
    """ConfiguracionFiscal (singleton). Import diferido: lib/ no acopla Django."""
    from ajustes.models import ConfiguracionFiscal
    return ConfiguracionFiscal.obtener()


def desglose_honorarios(base, cfg=None) -> dict:
    """Desglose RESICO / honorarios sobre `base` (importe antes de impuestos).

    Devuelve montos ya cuantizados + `impuestos_detalle` con la MISMA forma que
    el mecanismo genérico (para que signals de Contaduría los mapeen igual: el
    slot de cuenta se deriva de `nombre`/`tipo` — 'ISR' en el nombre → ISR
    retenido; retención sin 'ISR' → IVA retenido por pagar).
    """
    cfg = cfg or _config()
    base = q2(base)

    iva = q2(base * cfg.iva_tasa / CIEN)
    ret_isr = q2(base * cfg.ret_isr_honorarios / CIEN)
    # Retención de IVA = fracción exacta (num/den, típico ⅔) del IVA trasladado.
    # Se calcula del IVA ya redondeado (= "IVA trasladado calculado", pedido LC).
    num = Decimal(cfg.ret_iva_honorarios_num or 2)
    den = Decimal(cfg.ret_iva_honorarios_den or 3)
    ret_iva = q2(iva * num / den) if den else Decimal("0.00")

    trasladados = iva
    retenciones = q2(ret_isr + ret_iva)
    total = q2(base + iva - ret_isr - ret_iva)

    iva_lbl = f"{cfg.iva_tasa:g}"
    isr_lbl = f"{cfg.ret_isr_honorarios:g}"
    impuestos_detalle = [
        {"id": None, "tasa_id": None, "nombre": f"IVA trasladado ({iva_lbl}%)",
         "tipo": "trasladado", "porcentaje": cfg.iva_tasa, "monto": iva},
        {"id": None, "tasa_id": None, "nombre": f"Retención de ISR ({isr_lbl}%)",
         "tipo": "retencion", "porcentaje": cfg.ret_isr_honorarios, "monto": ret_isr},
        {"id": None, "tasa_id": None,
         "nombre": f"Retención de IVA ({cfg.ret_iva_honorarios_num}/{cfg.ret_iva_honorarios_den} del IVA)",
         "tipo": "retencion", "porcentaje": None, "monto": ret_iva},
    ]
    return {
        "iva": iva,
        "ret_isr": ret_isr,
        "ret_iva": ret_iva,
        "trasladados": trasladados,
        "retenciones": retenciones,
        "total": total,
        "impuestos_detalle": impuestos_detalle,
    }
