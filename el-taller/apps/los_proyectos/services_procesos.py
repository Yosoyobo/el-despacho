"""Sincronización de procesos (impresión + operativos) de un producto.

S-LC-Proyecto-Render-V1. El front serializa los procesos de cada tarjeta de
producto en un campo oculto `procesos_json`. Tras guardar el formset, la
vista llama a `sincronizar_procesos(producto, json_str)` por cada línea.

Estrategia (S-LC-Proyecto-V2): reconciliación en sitio preservando el FK
`egreso`. Antes se borraban y recreaban TODOS los procesos en cada autosave,
lo que perdía el vínculo con el egreso ya registrado — un gasto registrado
"reaparecía" como pendiente y se podía duplicar. Ahora los procesos existentes
se emparejan por tipo + orden de aparición y se ACTUALIZAN en sitio (sin tocar
su columna `egreso`); solo se crean/borran los sobrantes. Defensivo: JSON
inválido ⇒ no toca nada.
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

    # 1) Normaliza el JSON a la lista de procesos deseados.
    deseados = []
    for fila in data:
        if not isinstance(fila, dict):
            continue
        tipo = fila.get("tipo")
        if tipo not in TIPOS_VALIDOS:
            continue
        costo = _to_decimal(fila.get("costo"))
        proveedor_id = fila.get("proveedor_id")
        descripcion = (fila.get("descripcion") or "").strip()[:200]
        por_pieza = bool(fila.get("por_pieza"))
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
        deseados.append({
            "tipo": tipo, "proveedor_id": proveedor_id,
            "descripcion": descripcion, "costo": costo, "por_pieza": por_pieza,
        })

    # 2) Reconcilia contra los existentes (emparejados por tipo + orden de
    #    aparición), actualizando en sitio para PRESERVAR el FK `egreso`.
    existentes = list(producto.procesos.all().order_by("orden", "creado_en"))
    cola = {"impresion": [], "operativo": []}
    for p in existentes:
        cola.get(p.tipo, cola["operativo"]).append(p)
    idx = {"impresion": 0, "operativo": 0}
    conservados = set()
    for orden, d in enumerate(deseados):
        tipo = d["tipo"]
        pendientes = cola[tipo]
        i = idx[tipo]
        if i < len(pendientes):
            p = pendientes[i]
            p.orden = orden
            p.proveedor_id = d["proveedor_id"]
            p.descripcion = d["descripcion"]
            p.costo = d["costo"]
            p.por_pieza = d["por_pieza"]
            p.save(update_fields=["orden", "proveedor_id", "descripcion", "costo", "por_pieza"])
            conservados.add(p.pk)
            idx[tipo] = i + 1
        else:
            ProyectoProductoProceso.objects.create(
                producto=producto, tipo=tipo, orden=orden,
                proveedor_id=d["proveedor_id"], descripcion=d["descripcion"],
                costo=d["costo"], por_pieza=d["por_pieza"],
            )

    # 3) Borra los existentes que ya no aparecen en el JSON.
    for p in existentes:
        if p.pk not in conservados:
            p.delete()
