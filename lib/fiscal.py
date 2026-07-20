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
HALF_EVEN por defecto de Python).

**Anexo 20 SAT (Sprint Fiscal 2026-07):** cada impuesto se calcula de forma
100% INDEPENDIENTE = Base × (tasa nominal / 100), y se redondea al final. La
retención de IVA dejó de calcularse como fracción (⅔) del IVA ya redondeado —
que no cuadraba con el PAC — y ahora usa su tasa nominal (10.6667% = ⅔ de 16%)
directamente sobre la Base. Caso de auditoría (importe 33,770.00):

    Importe               33,770.00
    + IVA 16%              5,403.20   (33,770 × 16%      = 5,403.20)
    - Ret. ISR 1.25%         422.13   (33,770 × 1.25%    = 422.125  → 422.13)
    - Ret. IVA 10.6667%    3,602.14   (33,770 × 10.6667% = 3,602.1446 → 3,602.14)
    = Total neto          35,148.93

Facturas reales verificadas (Base → Ret. IVA → Total):
    16,000.00  → 1,706.67 → 16,653.33
    40,184.22  → 4,286.33 → 41,825.07
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

    # Anexo 20: cada impuesto es independiente = Base × tasa nominal / 100,
    # redondeado al final. (No se calcula la retención como fracción del IVA.)
    ret_iva_tasa = cfg.ret_iva_honorarios or Decimal("10.6667")
    iva = q2(base * cfg.iva_tasa / CIEN)
    ret_isr = q2(base * cfg.ret_isr_honorarios / CIEN)
    ret_iva = q2(base * ret_iva_tasa / CIEN)

    trasladados = iva
    retenciones = q2(ret_isr + ret_iva)
    total = q2(base + iva - ret_isr - ret_iva)

    iva_lbl = f"{cfg.iva_tasa:g}"
    isr_lbl = f"{cfg.ret_isr_honorarios:g}"
    ret_iva_lbl = f"{ret_iva_tasa:g}"
    impuestos_detalle = [
        {"id": None, "tasa_id": None, "nombre": f"IVA trasladado ({iva_lbl}%)",
         "tipo": "trasladado", "porcentaje": cfg.iva_tasa, "monto": iva},
        {"id": None, "tasa_id": None, "nombre": f"Retención de ISR ({isr_lbl}%)",
         "tipo": "retencion", "porcentaje": cfg.ret_isr_honorarios, "monto": ret_isr},
        {"id": None, "tasa_id": None,
         "nombre": f"Retención de IVA ({ret_iva_lbl}%)",
         "tipo": "retencion", "porcentaje": ret_iva_tasa, "monto": ret_iva},
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
