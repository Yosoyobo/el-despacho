"""Sincronización de procesos (impresión + operativos) de un producto.

S-LC-Proyecto-Render-V1. El front serializa los procesos de cada tarjeta de
producto en un campo oculto `procesos_json`. Tras guardar el formset, la
vista llama a `sincronizar_procesos(producto, json_str)` por cada línea.

Estrategia simple e idempotente: se borran los procesos actuales del producto
y se recrean desde el JSON validado (son pocos por producto). Se ignoran
filas sin costo y sin contenido. Defensivo: JSON inválido ⇒ no toca nada.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from apps.el_catalogo.models import Proveedor

from .models import ProyectoProductoProceso

TIPOS_VALIDOS = {"impresion", "operativo"}


def _to_decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def sincronizar_procesos(producto, procesos_json: str | None) -> None:
    """Reemplaza los procesos del producto con los del JSON.

    Formato esperado: lista de objetos
      {"tipo": "impresion"|"operativo", "proveedor_id": int|null,
       "descripcion": str, "costo": número}
    """
    if procesos_json is None:
        return
    try:
        data = json.loads(procesos_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, list):
        return

    # Proveedores activos válidos (whitelist anti-inyección de IDs).
    ids_validos = set(
        Proveedor.objects.filter(activo=True).values_list("pk", flat=True)
    )

    nuevos = []
    orden = 0
    for fila in data:
        if not isinstance(fila, dict):
            continue
        tipo = fila.get("tipo")
        if tipo not in TIPOS_VALIDOS:
            continue
        costo = _to_decimal(fila.get("costo"))
        proveedor_id = fila.get("proveedor_id")
        descripcion = (fila.get("descripcion") or "").strip()[:200]
        if tipo == "impresion":
            if proveedor_id not in ids_validos:
                proveedor_id = None
            # Impresión sin proveedor ni costo: nada que guardar.
            if proveedor_id is None and costo == 0:
                continue
            descripcion = ""
        else:  # operativo
            proveedor_id = None
            # Operativo sin descripción ni costo: nada que guardar.
            if not descripcion and costo == 0:
                continue
        nuevos.append(ProyectoProductoProceso(
            producto=producto,
            tipo=tipo,
            orden=orden,
            proveedor_id=proveedor_id,
            descripcion=descripcion,
            costo=costo,
        ))
        orden += 1

    producto.procesos.all().delete()
    if nuevos:
        ProyectoProductoProceso.objects.bulk_create(nuevos)
