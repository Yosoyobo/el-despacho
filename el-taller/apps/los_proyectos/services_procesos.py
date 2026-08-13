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

# Tope defensivo de procesos de venta por línea (LC 2026-07-26).
MAX_VENTAS = 20


def _to_decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


# LC 2026-08-04 (Oscar): el costo se puede capturar como una CUENTA —
# «35+15+15» por tres bordados. Se acepta una cadena de sumas, restas y
# multiplicaciones de números (nada de paréntesis ni `eval`), y el SERVIDOR es
# quien saca el total: así el monto que se guarda siempre concuerda con la
# cuenta escrita, aunque el POST llegue de otra parte.
#
# LC 2026-08-12 (Oscar): se suma la multiplicación — «15.75*100». Lo que se
# sigue rechazando es la DIVISIÓN, y no por descuido: con dos decimales pierde
# centavos (repartir 150 entre 29 da 5.17 × 29 = 149.93, no 150). Ése fue el
# error que ya nos costó una vez.
MAX_EXPR = 120
_SIGNOS = "+-"
_MULT = "*"


def suma_expresion(texto) -> Decimal | None:
    """Total de una cuenta tipo `35+15+15` o `15.75*100`. None si no es cuenta.

    Un número pelón (`65` o `65.00`) también devuelve su valor — así el mismo
    campo sirve para las dos formas de capturar. La multiplicación va primero,
    como en la aritmética de siempre: `2*3+4` son 10.
    """
    if texto is None:
        return None
    crudo = str(texto).replace(",", "").replace(" ", "")
    if not crudo or len(crudo) > MAX_EXPR:
        return None
    if any(c not in "0123456789." + _SIGNOS + _MULT for c in crudo):
        return None
    # Términos con su signo. Si al re-pegarlos no sale la cadena original, la
    # cuenta está mal escrita (`35++15`, `35+`, `.`) y se descarta completa.
    terminos = []
    actual = ""
    for i, c in enumerate(crudo):
        if c in _SIGNOS and i > 0:
            terminos.append(actual)
            actual = c
        else:
            actual += c
    terminos.append(actual)
    if "".join(terminos) != crudo:
        return None
    total = Decimal("0")
    for t in terminos:
        signo = Decimal("-1") if t.startswith("-") else Decimal("1")
        cuerpo = t.lstrip(_SIGNOS)
        if not cuerpo:
            return None
        producto = Decimal("1")
        factores = cuerpo.split(_MULT)
        for factor in factores:
            # `35*`, `*15` o `2**3` dejan un factor vacío: cuenta mal escrita.
            if not factor or factor.count(".") > 1 or factor == ".":
                return None
            try:
                producto *= Decimal(factor)
            except InvalidOperation:
                return None
        total += signo * producto
    return total.quantize(Decimal("0.01"))


def _expr_y_costo(fila: dict) -> tuple[str, Decimal]:
    """Normaliza el par (cuenta escrita, total). El total lo manda la cuenta."""
    expr = (str(fila.get("costo_expr") or "")).strip()[:MAX_EXPR]
    # Sin operadores no es una cuenta, es un número: no vale la pena conservarla.
    if expr and not any(c in _SIGNOS + _MULT for c in expr[1:]):
        expr = ""
    if expr:
        total = suma_expresion(expr)
        if total is not None:
            return expr, total
        expr = ""  # cuenta ilegible: se descarta y manda el número
    return expr, _to_decimal(fila.get("costo"))


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
        # LC 2026-08-04: el costo puede venir como una cuenta escrita («35+15+15»).
        costo_expr, costo = _expr_y_costo(fila)
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
            # Ticket UX 2026-07 (@proveedor): un gasto operativo PUEDE ligar un
            # proveedor (opcional) vía el disparador @; su costo se suma a la
            # deuda de ese proveedor. Se valida contra proveedores activos.
            if proveedor_id not in ids_validos:
                proveedor_id = None
            # Operativo sin descripción ni costo: nada que guardar.
            if not descripcion and costo == 0:
                continue
        deseados.append({
            "tipo": tipo, "proveedor_id": proveedor_id,
            "descripcion": descripcion, "costo": costo, "por_pieza": por_pieza,
            "costo_expr": costo_expr,
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
            p.costo_expr = d["costo_expr"]
            p.por_pieza = d["por_pieza"]
            p.save(update_fields=["orden", "proveedor_id", "descripcion", "costo", "costo_expr", "por_pieza"])
            conservados.add(p.pk)
            idx[tipo] = i + 1
        else:
            ProyectoProductoProceso.objects.create(
                producto=producto, tipo=tipo, orden=orden,
                proveedor_id=d["proveedor_id"], descripcion=d["descripcion"],
                costo=d["costo"], costo_expr=d["costo_expr"],
                por_pieza=d["por_pieza"],
            )

    # 3) Borra los existentes que ya no aparecen en el JSON.
    for p in existentes:
        if p.pk not in conservados:
            p.delete()


# ── Procesos de VENTA (LC 2026-07-26, Oscar) ─────────────────────────────────
#
# Mismo patrón que los de producción: el front los serializa en un campo oculto
# `ventas_json` de la tarjeta y la vista llama a `sincronizar_ventas` tras
# guardar el formset. La diferencia es qué significan: éstos se le COBRAN al
# cliente (cada uno es una línea propia de la cotización), no cuestan.
#
# Reconciliación en sitio por orden de aparición (no borrar-y-recrear) para que
# el pk sobreviva los autosaves.


def sincronizar_ventas(producto, ventas_json: str | None) -> None:
    """Reemplaza los procesos de venta del producto con los del JSON.

    Formato esperado: lista de objetos
      {"descripcion": str, "cantidad": int, "precio": número}

    Defensivo: JSON inválido ⇒ no toca nada. Una fila sin descripción y sin
    precio se ignora (es una fila vacía que el usuario nunca llenó).
    """
    from .models import ProyectoProductoVenta

    if ventas_json is None:
        return
    try:
        data = json.loads(ventas_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, list):
        return

    deseados = []
    for fila in data[:MAX_VENTAS]:
        if not isinstance(fila, dict):
            continue
        descripcion = (fila.get("descripcion") or "").strip()[:200]
        precio = _to_decimal(fila.get("precio"))
        if precio < 0:
            precio = Decimal("0.00")
        try:
            cantidad = int(fila.get("cantidad") or 1)
        except (TypeError, ValueError):
            cantidad = 1
        cantidad = max(1, min(cantidad, 1_000_000))
        if not descripcion and precio == 0:
            continue
        deseados.append({"descripcion": descripcion, "cantidad": cantidad,
                         "precio_unitario": precio})

    existentes = list(producto.ventas.all().order_by("orden", "creado_en"))
    conservados = set()
    for orden, d in enumerate(deseados):
        if orden < len(existentes):
            v = existentes[orden]
            v.orden = orden
            v.descripcion = d["descripcion"]
            v.cantidad = d["cantidad"]
            v.precio_unitario = d["precio_unitario"]
            v.save(update_fields=["orden", "descripcion", "cantidad", "precio_unitario"])
            conservados.add(v.pk)
        else:
            ProyectoProductoVenta.objects.create(
                producto=producto, orden=orden, descripcion=d["descripcion"],
                cantidad=d["cantidad"], precio_unitario=d["precio_unitario"],
            )

    for v in existentes:
        if v.pk not in conservados:
            v.delete()
