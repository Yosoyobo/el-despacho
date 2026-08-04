"""Descripción de cada concepto de la cotización (LC 2026-07).

Formato que pidió Oscar, tal como lo escribe hoy a mano:

    105 pz (3 colores, 35 pz c/u)
    Gorras de gabardina 100% algodón deslavado
    Color: Beige / Terracota / Café
    Con bordado frontal y trasero
    Frontal: Mantarraya - 4.5 - 5 cm de ancho

Este módulo genera el **esqueleto** (las piezas y lo que ya sabe el catálogo) y
el resto se escribe en la página de la cotización, donde vive el texto. Es
deliberadamente simple: el detalle fino de branding lo pone una persona, no una
heurística.

Dos reglas del sprint:

- **El texto se congela por versión.** Lo que se generó para la v2 no cambia
  aunque después se toque el catálogo.
- **La versión siguiente HEREDA el texto editado.** Si en la v2 escribiste
  «Frontal: Mantarraya - 4.5 cm», la v3 lo conserva; sólo se refresca el número
  de piezas del primer renglón si la cantidad cambió, preservando lo que hayas
  escrito entre paréntesis.
"""

from __future__ import annotations

import re

# «105 pz», «1,050 pz», «8 PZ …» al inicio del primer renglón. El resto del
# renglón (p.ej. « (3 colores, 35 pz c/u)») se conserva intacto.
_RE_PIEZAS = re.compile(r"^(\s*)([\d.,]+)(\s*pz\b)", re.IGNORECASE)


def _piezas(pp) -> int:
    """Piezas que se le cobran al cliente (la merma no se cotiza)."""
    return int(pp.cantidad or 0)


def _especificacion(pp) -> str:
    """Especificación del elemento: la que se escribió en la TARJETA del proyecto
    o, si está vacía, la que trae el producto del catálogo.

    LC 2026-08-04 (Oscar): el campo «Descripción» de la tarjeta de producto está
    **ligado a la especificación del elemento que se pone en la cotización». Es un
    override por línea, el mismo patrón que `precio_unitario` / `costo_unitario` /
    `nombre_proyecto`: lo del proyecto manda; el catálogo es el respaldo.
    """
    propia = (getattr(pp, "nota", "") or "").strip()
    if propia:
        return propia
    if pp.servicio_id:
        return (pp.servicio.descripcion_default or "").strip()
    return ""


def esqueleto(pp) -> str:
    """Descripción inicial de una línea de producto del proyecto."""
    renglones = [f"{_piezas(pp)} pz"]
    base = _especificacion(pp)
    renglones += [r.strip() for r in base.splitlines() if r.strip()]
    return "\n".join(renglones)


def refrescar_piezas(texto: str, pp) -> str:
    """Actualiza el conteo de piezas del primer renglón, sin tocar el resto.

    «105 pz (3 colores, 35 pz c/u)» con cantidad 110 → «110 pz (3 colores,
    35 pz c/u)». Si el primer renglón no habla de piezas, se le antepone uno
    que sí (el texto viejo se conserva completo).
    """
    piezas = _piezas(pp)
    renglones = (texto or "").splitlines()
    if not renglones:
        return f"{piezas} pz"
    m = _RE_PIEZAS.match(renglones[0])
    if m:
        renglones[0] = _RE_PIEZAS.sub(rf"\g<1>{piezas}\g<3>", renglones[0], count=1)
    else:
        renglones.insert(0, f"{piezas} pz")
    return "\n".join(renglones)


def descripcion_para(pp, previo: str = "") -> str:
    """Texto de la línea: hereda el editado de la versión anterior (con las
    piezas al día) o, si no hay, genera el esqueleto."""
    if (previo or "").strip():
        return refrescar_piezas(previo, pp)
    return esqueleto(pp)


def indice_previo(cotizacion) -> dict:
    """Índice de los textos de la versión anterior para heredarlos.

    Llaves: `("srv", servicio_id, variacion_id)` y, como respaldo cuando el
    producto se cambió de línea, el nombre del concepto en minúsculas.
    """
    if cotizacion is None:
        return {}
    indice: dict = {}
    for it in cotizacion.items.all():
        texto = (it.descripcion or "").strip()
        if not texto:
            continue
        indice.setdefault(("srv", it.servicio_id, it.variacion_id), texto)
        nombre = it.concepto_visible.strip().lower()
        if nombre:
            indice.setdefault(("nom", nombre), texto)
    return indice


def heredado(indice: dict, pp) -> str:
    """Texto de la versión anterior que corresponde a esta línea, si existe."""
    if not indice:
        return ""
    por_producto = indice.get(("srv", pp.servicio_id, pp.variacion_id))
    if por_producto:
        return por_producto
    return indice.get(("nom", pp.nombre_visible.strip().lower()), "")


__all__ = [
    "esqueleto",
    "refrescar_piezas",
    "descripcion_para",
    "indice_previo",
    "heredado",
]
