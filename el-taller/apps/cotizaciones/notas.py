"""Notas al pie de la cotización (LC 2026-07).

Decisión de Oscar: **las notas van siempre, tal cual.** No son editables ni
opcionales — son las condiciones con las que Learning Center cotiza, y salir
sin ellas cambiaría lo que el cliente está aceptando. Lo único que se mueve es
la última, que depende del interruptor Anticipo / Un solo pago de la cotización.

Si algún día hacen falta condiciones extra para un cliente puntual, se capturan
en `Cotizacion.terminos` y el PDF las agrega como bloque aparte, debajo.
"""

from __future__ import annotations

NOTAS_FIJAS: tuple[str, ...] = (
    "Precios unitarios de producción.",
    "Todo detalle está abierto a cambios, nuevas ideas y necesidades.",
    "Las imágenes son ilustrativas y no representan productos finales exactos.",
    "Debido a procesos manuales y características de los materiales, pueden "
    "existir leves variaciones en color, tamaño y acabado respecto a "
    "indicaciones o referencias.",
    "No nos hacemos responsables por retrasos ocasionados por proveedores "
    "externos o causas de fuerza mayor.",
    "Todos los productos sujetos a existencias.",
    "Los precios no incluyen IVA.",
)


def notas_para(cotizacion) -> list[str]:
    """Las notas del documento, en orden. La última es la forma de pago."""
    return [*NOTAS_FIJAS, cotizacion.nota_forma_pago]


__all__ = ["NOTAS_FIJAS", "notas_para"]
