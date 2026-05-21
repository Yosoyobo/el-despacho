"""Mapeo de TasaImpositiva → slot de cuenta contable.

Se usa al generar el asiento `auto_factura_emitida`. El catálogo de tasas
no tiene `codigo_impuesto`, así que se inspecciona el `nombre` (heurística:
si contiene "ISR" → cuenta de ISR retenido) y `tipo` (trasladado vs
retención).
"""

from __future__ import annotations


def mapa_iva_para_tasa(tasa) -> str:
    """Retorna el slot de cuenta para una `TasaImpositiva`.

    - trasladado → 'iva_trasladado'
    - retención + nombre contiene 'ISR' → 'isr_retenido'
    - retención otro → 'iva_retenido_pagar'
    """
    tipo = (tasa.tipo or "").lower()
    nombre = (getattr(tasa, "nombre", "") or "").lower()
    if tipo == "trasladado":
        return "iva_trasladado"
    if tipo == "retencion":
        if "isr" in nombre:
            return "isr_retenido"
        return "iva_retenido_pagar"
    return ""
