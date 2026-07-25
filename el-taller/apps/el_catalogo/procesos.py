"""Impresión + procesos adicionales del PRODUCTO (plantilla del catálogo).

LC 2026-07-25 (Oscar): en la ficha del producto se capturan su impresión y sus
procesos/gastos adicionales; al elegir ese producto en un proyecto la tarjeta se
pre-llena con ellos (y ahí se editan libremente).

Se guardan en `Servicio.procesos_default` con la MISMA forma que el
`procesos_json` de la línea de proyecto, para que el JS del proyecto los aplique
sin traducción:

    [{"tipo": "impresion", "proveedor_id": 3, "costo": "12.50", "por_pieza": true},
     {"tipo": "operativo", "descripcion": "Clavos", "costo": "30.00",
      "por_pieza": false, "proveedor_id": null}]

**No** se suman a `Servicio.costo`: el proyecto cuenta los procesos por separado
(ver `apps.los_proyectos.gastos`), así que sumarlos aquí duplicaría el gasto. En
la ficha se muestra un total informativo.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

MAX_PROCESOS = 20
CERO = Decimal("0.00")


def _monto(valor) -> Decimal:
    try:
        d = Decimal(str(valor or 0))
    except (InvalidOperation, ValueError, TypeError):
        return CERO
    return CERO if d < 0 else d.quantize(Decimal("0.01"))


def _proveedor_valido(pk) -> int | None:
    """Solo IDs de proveedores activos (el JSON llega del navegador)."""
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    from .models import Proveedor
    return pk if Proveedor.objects.filter(pk=pk, activo=True).exists() else None


def parsear(post) -> list[dict]:
    """Normaliza el JSON del form (`procesos_default_json`) → lista saneada.

    Defensivo: JSON inválido, tipos raros o montos negativos ⇒ se descartan sin
    lanzar (el producto se guarda igual, solo sin esos procesos).
    """
    crudo = (post.get("procesos_default_json") or "").strip()
    if not crudo:
        return []
    try:
        datos = json.loads(crudo)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(datos, list):
        return []
    salida: list[dict] = []
    for item in datos[:MAX_PROCESOS]:
        if not isinstance(item, dict):
            continue
        tipo = "impresion" if item.get("tipo") == "impresion" else "operativo"
        costo = _monto(item.get("costo"))
        prov = _proveedor_valido(item.get("proveedor_id"))
        por_pieza = bool(item.get("por_pieza"))
        if tipo == "impresion":
            # La impresión sin proveedor no aporta nada (el gasto se le adeuda a
            # alguien). Solo una impresión por producto.
            if prov is None or any(p["tipo"] == "impresion" for p in salida):
                continue
            salida.append({
                "tipo": "impresion", "proveedor_id": prov,
                "costo": str(costo), "por_pieza": por_pieza,
            })
            continue
        desc = str(item.get("descripcion") or "").strip()[:200]
        if not desc and costo <= 0:
            continue
        salida.append({
            "tipo": "operativo", "descripcion": desc, "costo": str(costo),
            "por_pieza": por_pieza, "proveedor_id": prov,
        })
    return salida


def normalizados(servicio) -> list[dict]:
    """Los procesos guardados, tolerando datos viejos/corruptos."""
    datos = getattr(servicio, "procesos_default", None) or []
    return [p for p in datos if isinstance(p, dict)]


def impresion_de(servicio) -> dict | None:
    return next((p for p in normalizados(servicio) if p.get("tipo") == "impresion"), None)


def operativos_de(servicio) -> list[dict]:
    return [p for p in normalizados(servicio) if p.get("tipo") != "impresion"]


def costo_extra(servicio, piezas: int = 1) -> Decimal:
    """Suma informativa de los procesos para `piezas` producidas.

    Los `por_pieza` se multiplican; los fijos se suman tal cual. Informativo —
    no toca `Servicio.costo`.
    """
    piezas = max(int(piezas or 1), 1)
    total = CERO
    for p in normalizados(servicio):
        c = _monto(p.get("costo"))
        total += c * piezas if p.get("por_pieza") else c
    return total.quantize(Decimal("0.01"))


__all__ = [
    "costo_extra", "impresion_de", "normalizados", "operativos_de", "parsear",
]
