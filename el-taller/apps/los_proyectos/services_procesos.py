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
import re
from decimal import Decimal, InvalidOperation

from apps.el_catalogo.models import Proveedor

from .models import MAX_ESCALAS, MAX_EXTRAS, ProyectoProductoProceso

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
# LC 2026-08-12 (Oscar): se suma la multiplicación — «15.75*100».
#
# LC 2026-08-18 (Oscar): y la DIVISIÓN, que hasta hoy se rechazaba a propósito.
# La razón del veto sigue siendo cierta —con dos decimales pierde centavos:
# repartir 150 entre 29 da 5.17, y 5.17 × 29 son 149.93, no 150— así que ahora
# se paga con transparencia en vez de con una prohibición: la división se
# calcula a precisión completa y sólo se redondea al final, y la tarjeta pinta
# el resultado en chiquito bajo el campo («= $5.17») para que el redondeo se
# vea ANTES de guardar. Quien escribe la cuenta decide.
MAX_EXPR = 120
_SIGNOS = "+-"
_MULT = "*"
_DIV = "/"
_FACTORES = _MULT + _DIV


def suma_expresion(texto) -> Decimal | None:
    """Total de una cuenta tipo `35+15+15`, `15.75*100` o `150/29`.

    None si no es una cuenta legible. Un número pelón (`65` o `65.00`) también
    devuelve su valor — así el mismo campo sirve para las dos formas de
    capturar. Multiplicaciones y divisiones van primero, como en la aritmética
    de siempre (`2*3+4` son 10), y entre ellas de izquierda a derecha
    (`100/4*3` son 75). El redondeo a centavos se hace UNA sola vez, al final:
    `150/29*29` da los 150 exactos aunque el paso intermedio no sea redondo.
    """
    if texto is None:
        return None
    crudo = str(texto).replace(",", "").replace(" ", "")
    if not crudo or len(crudo) > MAX_EXPR:
        return None
    if any(c not in "0123456789." + _SIGNOS + _FACTORES for c in crudo):
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
        # Factores con su operador: `100/4*3` → 100, (/ 4), (* 3).
        piezas = re.split(f"([{re.escape(_FACTORES)}])", cuerpo)
        producto = Decimal("1")
        operador = _MULT
        for i, pieza in enumerate(piezas):
            if i % 2:                       # posición impar = el operador
                operador = pieza
                continue
            # `35*`, `*15` o `2**3` dejan un factor vacío: cuenta mal escrita.
            if not pieza or pieza.count(".") > 1 or pieza == ".":
                return None
            try:
                valor = Decimal(pieza)
            except InvalidOperation:
                return None
            if operador == _DIV:
                if valor == 0:              # entre cero no hay cuenta que valga
                    return None
                producto /= valor
            else:
                producto *= valor
        total += signo * producto
    return total.quantize(Decimal("0.01"))


def _expr_y_costo(fila: dict, clave: str = "costo") -> tuple[str, Decimal]:
    """Normaliza el par (cuenta escrita, total). El total lo manda la cuenta.

    `clave` permite reusar la regla en otros campos que también aceptan cuenta
    (`costo_unitario`, `impresion_costo` de las escalas de volumen).
    """
    expr = (str(fila.get(f"{clave}_expr") or "")).strip()[:MAX_EXPR]
    # Sin operadores no es una cuenta, es un número: no vale la pena conservarla.
    if expr and not any(c in _SIGNOS + _FACTORES for c in expr[1:]):
        expr = ""
    if expr:
        total = suma_expresion(expr)
        if total is not None:
            return expr, total
        expr = ""  # cuenta ilegible: se descarta y manda el número
    return expr, _to_decimal(fila.get(clave))


def _expr_y_costo_opcional(fila: dict, clave: str) -> tuple[str, Decimal | None]:
    """Igual que `_expr_y_costo`, pero **vacío devuelve None**.

    Es la semántica de las escalas de volumen: un campo en blanco HEREDA de la
    Opción A, mientras que un 0 escrito es un cero de verdad («esta escala no
    lleva impresión»). Por eso no se puede usar el 0 como centinela.
    """
    crudo = fila.get(clave)
    expr_crudo = str(fila.get(f"{clave}_expr") or "").strip()
    if not expr_crudo and (crudo is None or str(crudo).strip() == ""):
        return "", None
    return _expr_y_costo(fila, clave)


def procesos_normalizados(procesos_json: str | None) -> list[dict] | None:
    """Valida el JSON de procesos y devuelve la lista deseada.

    `None` significa «no toques nada» (no llegó JSON, o es ilegible). Es la
    fuente única de las reglas —whitelist de tipos, proveedor activo, la cuenta
    escrita manda sobre el total— y la comparten el sincronizador de la línea
    viva y la foto por versión (S-Ajustes-Ago12-B).

    Formato esperado: lista de objetos
      {"tipo": "impresion"|"operativo", "proveedor_id": int|null,
       "descripcion": str, "costo": número}
    """
    if procesos_json is None:
        return None
    try:
        data = json.loads(procesos_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None

    # Proveedores activos válidos (whitelist anti-inyección de IDs).
    ids_validos = set(
        Proveedor.objects.filter(activo=True).values_list("pk", flat=True)
    )

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
    return deseados


def sincronizar_procesos(producto, procesos_json: str | None) -> None:
    """Reemplaza los procesos del producto con los del JSON."""
    deseados = procesos_normalizados(procesos_json)
    if deseados is None:
        return

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


def ventas_normalizadas(ventas_json: str | None) -> list[dict] | None:
    """Valida el JSON de procesos de venta y devuelve la lista deseada.

    `None` = no toques nada (sin JSON o ilegible). Una fila sin descripción y sin
    precio se ignora: es una fila vacía que el usuario nunca llenó.

    Formato esperado: lista de objetos
      {"descripcion": str, "cantidad": int, "precio": número}
    """
    if ventas_json is None:
        return None
    try:
        data = json.loads(ventas_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None

    deseados = []
    for fila in data[:MAX_VENTAS]:
        if not isinstance(fila, dict):
            continue
        descripcion = (fila.get("descripcion") or "").strip()[:200]
        # LC 2026-08-18: el precio de un proceso de venta también admite cuenta.
        precio_expr, precio = _expr_y_costo(fila, "precio")
        if precio < 0:
            precio, precio_expr = Decimal("0.00"), ""
        try:
            cantidad = int(fila.get("cantidad") or 1)
        except (TypeError, ValueError):
            cantidad = 1
        cantidad = max(1, min(cantidad, 1_000_000))
        if not descripcion and precio == 0:
            continue
        deseados.append({"descripcion": descripcion, "cantidad": cantidad,
                         "precio_unitario": precio, "precio_expr": precio_expr})
    return deseados


def _entero(valor, *, minimo: int, default: int) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return default
    return max(minimo, min(n, 1_000_000))


def escalas_normalizadas(escalas_json: str | None) -> list[dict] | None:
    """Valida el JSON de escalas de volumen y devuelve la lista deseada.

    `None` = no toques nada (sin JSON o ilegible). Fuente única de las reglas,
    compartida por la línea viva y la foto por versión.

    Formato esperado: lista de objetos
      {"cantidad": int, "merma": int,
       "precio_unitario": número|"", "costo_unitario": número|"",
       "costo_unitario_expr": str, "impresion_costo": número|"",
       "impresion_costo_expr": str, "impresion_por_pieza": bool,
       "extras": [{"costo": número, "costo_expr": str, "por_pieza": bool}],
       "activa": bool, "visible_pdf": bool}

    Dos invariantes que se imponen aquí y no en el front:

    - **Vacío hereda, 0 es cero** (ver `_expr_y_costo_opcional`).
    - **Una sola activa**: si el JSON trae varias, gana la primera. La base
      además lo garantiza con un `UniqueConstraint` parcial.
    """
    if escalas_json is None:
        return None
    try:
        data = json.loads(escalas_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None

    deseados: list[dict] = []
    ya_hay_activa = False
    for fila in data[:MAX_ESCALAS]:
        if not isinstance(fila, dict):
            continue
        precio_expr, precio = _expr_y_costo_opcional(fila, "precio_unitario")
        costo_expr, costo = _expr_y_costo_opcional(fila, "costo_unitario")
        imp_expr, imp_costo = _expr_y_costo_opcional(fila, "impresion_costo")
        extras = []
        for extra in (fila.get("extras") or [])[:MAX_EXTRAS]:
            if not isinstance(extra, dict):
                continue
            e_expr, e_costo = _expr_y_costo(extra)
            if e_costo == 0:
                continue          # un extra en cero no aporta nada
            extras.append({"costo": str(e_costo), "costo_expr": e_expr,
                           "por_pieza": bool(extra.get("por_pieza"))})

        cantidad_cruda = fila.get("cantidad")
        vacia = (
            (cantidad_cruda is None or str(cantidad_cruda).strip() in ("", "0"))
            and precio is None and costo is None and imp_costo is None and not extras
        )
        if vacia:
            continue              # fila que se agregó y nunca se llenó

        activa = bool(fila.get("activa")) and not ya_hay_activa
        if activa:
            ya_hay_activa = True
        deseados.append({
            "cantidad": _entero(cantidad_cruda, minimo=1, default=1),
            "merma": _entero(fila.get("merma"), minimo=0, default=0),
            "precio_unitario": precio,
            "precio_unitario_expr": precio_expr,
            "costo_unitario": costo,
            "costo_unitario_expr": costo_expr,
            "impresion_costo": imp_costo,
            "impresion_costo_expr": imp_expr,
            "impresion_por_pieza": bool(fila.get("impresion_por_pieza")),
            "extras_json": extras,
            "activa": activa,
            # Default TRUE: una escala nace visible, como en el render.
            "visible_pdf": bool(fila.get("visible_pdf", True)),
        })
    return deseados


def sincronizar_escalas(producto, escalas_json: str | None) -> None:
    """Reemplaza las escalas de volumen del producto con las del JSON.

    Reconciliación en sitio por orden de aparición, como los procesos de venta.
    **Primero se apaga toda `activa`**: el `UniqueConstraint` parcial rechazaría
    un momento intermedio con dos activas (pasar la activa de la B a la C).
    """
    from .models import ProyectoProductoEscala

    deseados = escalas_normalizadas(escalas_json)
    if deseados is None:
        return

    existentes = list(producto.escalas.all().order_by("orden", "creado_en"))
    if existentes:
        producto.escalas.update(activa=False)

    activa_pk = None
    conservados = set()
    for orden, d in enumerate(deseados):
        campos = {k: v for k, v in d.items() if k != "activa"}
        if orden < len(existentes):
            e = existentes[orden]
            e.orden = orden
            e.activa = False
            for campo, valor in campos.items():
                setattr(e, campo, valor)
            e.save()
            conservados.add(e.pk)
        else:
            e = ProyectoProductoEscala.objects.create(
                producto=producto, orden=orden, activa=False, **campos)
        if d["activa"]:
            activa_pk = e.pk

    for e in existentes:
        if e.pk not in conservados:
            e.delete()

    if activa_pk is not None:
        ProyectoProductoEscala.objects.filter(pk=activa_pk).update(activa=True)


def sincronizar_ventas(producto, ventas_json: str | None) -> None:
    """Reemplaza los procesos de venta del producto con los del JSON."""
    from .models import ProyectoProductoVenta

    deseados = ventas_normalizadas(ventas_json)
    if deseados is None:
        return

    existentes = list(producto.ventas.all().order_by("orden", "creado_en"))
    conservados = set()
    for orden, d in enumerate(deseados):
        if orden < len(existentes):
            v = existentes[orden]
            v.orden = orden
            v.descripcion = d["descripcion"]
            v.cantidad = d["cantidad"]
            v.precio_unitario = d["precio_unitario"]
            v.precio_expr = d["precio_expr"]
            v.save(update_fields=["orden", "descripcion", "cantidad",
                                  "precio_unitario", "precio_expr"])
            conservados.add(v.pk)
        else:
            ProyectoProductoVenta.objects.create(
                producto=producto, orden=orden, descripcion=d["descripcion"],
                cantidad=d["cantidad"], precio_unitario=d["precio_unitario"],
                precio_expr=d["precio_expr"],
            )

    for v in existentes:
        if v.pk not in conservados:
            v.delete()
