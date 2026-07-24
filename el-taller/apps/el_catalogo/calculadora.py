"""Calculadora de costos por producto (2026-07).

Aplica solo a productos ligados a ciertos proveedores (hoy "Simil Cuero
Plymouth"). Captura tres grupos de insumos y arma el precio:

    Subtotal (antes de IVA) = (Σ sublimación + mano de obra) × factor + Σ material
    IVA                     = Subtotal × iva%
    Gran total              = Subtotal + IVA

El material (grupo 1) NUNCA se multiplica por el factor: solo se suma al final.
El Subtotal (antes de IVA) alimenta `Servicio.precio_base` (el IVA se aplica
después en cotización/factura, así que el precio se guarda SIN IVA).

Los insumos se guardan como strings en `Servicio.detalles_costo` (JSON) para
no chocar con la serialización de Decimal.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Nombre del proveedor cuyos productos muestran la calculadora. Match
# case-insensitive por `razon_social` (Proveedor no tiene slug estable).
PROVEEDOR_CALCULADORA = "Simil Cuero Plymouth"
FACTOR_DEFAULT = Decimal("2.2")
N_CAMPOS = 4  # campos por grupo (material / sublimación)


def _num(valor) -> Decimal:
    """Convierte a Decimal ≥ 0; cualquier basura → 0."""
    try:
        d = Decimal(str(valor).strip() or "0")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    return d if d >= 0 else Decimal("0")


def servicio_usa_calculadora(srv) -> bool:
    """True si el producto está ligado al proveedor de la calculadora."""
    return srv.proveedores.filter(razon_social__icontains=PROVEEDOR_CALCULADORA).exists()


def parsear_detalles(post) -> dict:
    """Lee los campos del POST (calc_material_N / calc_sublimacion_N /
    calc_mano_obra) y devuelve el dict a persistir en `detalles_costo`."""
    materiales = [_num(post.get(f"calc_material_{i}")) for i in range(N_CAMPOS)]
    sublimacion = [_num(post.get(f"calc_sublimacion_{i}")) for i in range(N_CAMPOS)]
    mano_obra = _num(post.get("calc_mano_obra"))
    return {
        "materiales": [str(x) for x in materiales],
        "sublimacion": [str(x) for x in sublimacion],
        "mano_obra": str(mano_obra),
        "factor": str(FACTOR_DEFAULT),
    }


def calcular(detalles: dict, iva_tasa: Decimal = Decimal("16")) -> dict:
    """Aplica la fórmula. `detalles` es el dict guardado (strings). Devuelve
    Decimals cuantizados a 2 decimales para el subtotal/iva/total."""
    materiales = [_num(x) for x in (detalles or {}).get("materiales", [])]
    sublimacion = [_num(x) for x in (detalles or {}).get("sublimacion", [])]
    mano_obra = _num((detalles or {}).get("mano_obra", 0))
    factor = _num((detalles or {}).get("factor", FACTOR_DEFAULT)) or FACTOR_DEFAULT
    m1 = sum(materiales, Decimal("0"))
    m2 = sum(sublimacion, Decimal("0"))
    subtotal = ((m2 + mano_obra) * factor + m1).quantize(Decimal("0.01"))
    iva = (subtotal * _num(iva_tasa) / Decimal("100")).quantize(Decimal("0.01"))
    total = (subtotal + iva).quantize(Decimal("0.01"))
    return {
        "m1": m1, "m2": m2, "mano_obra": mano_obra, "factor": factor,
        "subtotal": subtotal, "iva": iva, "total": total,
    }
