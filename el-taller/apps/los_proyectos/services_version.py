"""La foto de los productos por versión de cotización, y sus tres operaciones.

S-Ajustes-Ago12-B. Ver el docstring de `models.producto_version` para el porqué
de una tabla aparte y de guardar los valores ya resueltos.

- `fotografiar(cot, pares)` — al generar la versión, congela el lado del costo
  que la cotización no guarda (merma, costo, proveedor, procesos).
- `sincronizar_items(cot)` — al editar una pestaña, empuja al documento lo que ve
  el cliente (concepto, especificación, cantidad, precio y las líneas de venta),
  para que el PDF de esa versión siga coincidiendo con lo que muestra la pestaña.
  **El PDF de una cotización ya enviada cambia**: es el comportamiento que Oscar
  eligió sabiéndolo.
- `restaurar_en_edicion(cot, actor)` — repone los valores de esa versión en las
  líneas vivas del proyecto.

Los procesos y las ventas viajan como JSON con la MISMA forma que serializa la
tarjeta (`_form_productos_js.html`), así el editor se reutiliza sin traducir.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

CERO = Decimal("0.00")


# ── Serialización de procesos / ventas (la forma de la tarjeta) ───────────────

def procesos_json(pp) -> list[dict]:
    """Procesos de producción de una línea viva, como los serializa el front."""
    return [{
        "tipo": p.tipo,
        "proveedor_id": p.proveedor_id,
        "descripcion": p.descripcion or "",
        "costo": str(Decimal(str(p.costo or 0)).quantize(Decimal("0.01"))),
        "costo_expr": p.costo_expr or "",
        "por_pieza": bool(p.por_pieza),
    } for p in pp.procesos.all().order_by("orden", "creado_en")]


def ventas_json(pp) -> list[dict]:
    """Procesos de venta de una línea viva, como los serializa el front."""
    return [{
        "descripcion": v.descripcion or "",
        "cantidad": int(v.cantidad or 1),
        "precio": str(Decimal(str(v.precio_unitario or 0)).quantize(Decimal("0.01"))),
    } for v in pp.ventas.all().order_by("orden", "creado_en")]


def _opcional(valor) -> str | None:
    """Decimal a cadena, conservando el None. En las escalas un nulo significa
    «hereda de la Opción A», así que NO se puede aplanar a 0 (ver `models/escala`)."""
    if valor is None:
        return None
    return str(Decimal(str(valor)).quantize(Decimal("0.01")))


def escalas_json(pp) -> list[dict]:
    """Escalas de volumen de una línea viva, como las serializa el front.

    Se guardan con sus nulos intactos: la escala que heredaba de la Opción A
    debe seguir heredando cuando la pestaña se vuelva a pintar.
    """
    return [{
        "cantidad": int(e.cantidad or 1),
        "merma": int(e.merma or 0),
        "precio_unitario": _opcional(e.precio_unitario),
        "costo_unitario": _opcional(e.costo_unitario),
        "costo_unitario_expr": e.costo_unitario_expr or "",
        "impresion_costo": _opcional(e.impresion_costo),
        "impresion_costo_expr": e.impresion_costo_expr or "",
        "impresion_por_pieza": bool(e.impresion_por_pieza),
        "extras": list(e.extras_json or []),
        "activa": bool(e.activa),
        "visible_pdf": bool(e.visible_pdf),
    } for e in pp.escalas.all().order_by("orden", "creado_en")]


# ── Al generar la versión ────────────────────────────────────────────────────

def fotografiar(cot, pares) -> int:
    """Congela las líneas del proyecto de esta versión. Devuelve cuántas.

    `pares` son las parejas `(ProyectoProducto, CotizacionItem)` que acaba de
    crear el generador — el vínculo se sabe ahí, así que no hay que adivinarlo
    después. **No** se copia el FK `egreso` (es marca de idempotencia de la línea
    viva, igual que en `duplicar_producto`).
    """
    from .models import ProyectoProductoVersion

    filas = []
    for orden, (pp, item) in enumerate(pares):
        filas.append(ProyectoProductoVersion(
            cotizacion=cot,
            item=item,
            orden=orden,
            servicio_id=pp.servicio_id,
            variacion_id=pp.variacion_id,
            proveedor_id=pp.proveedor_id,
            nombre_proyecto=(pp.nombre_proyecto or "")[:150],
            cantidad=pp.cantidad or 0,
            merma=pp.merma or 0,
            # Resueltos, nunca heredados: un cambio de catálogo no debe reescribir
            # lo que se cotizó (ver el docstring del modelo).
            # `*_propio` y no `*_efectivo`: con una escala activa, el efectivo
            # ES el de la escala, y la fila A de la pestaña debe conservar lo
            # suyo (las escalas se congelan aparte, en `escalas_json`).
            precio_unitario=pp.precio_propio,
            costo_unitario=pp.costo_propio,
            costo_unitario_expr=(pp.costo_unitario_expr or ""),
            nota=(pp.nota or ""),
            imagen_file_id=pp.imagen_efectiva_file_id,
            incluir_en_calculo=True,
            procesos_json=procesos_json(pp),
            ventas_json=ventas_json(pp),
            escalas_json=escalas_json(pp),
            visible_pdf=bool(pp.visible_pdf),
            reconstruido=False,
        ))
    if filas:
        ProyectoProductoVersion.objects.bulk_create(filas)
    return len(filas)


# ── Empujar al documento lo que ve el cliente ────────────────────────────────

def _nombre_de(fila) -> str:
    return fila.nombre_visible


@transaction.atomic
def sincronizar_items(cot) -> None:
    """Reescribe las líneas de la cotización a partir de la foto editada.

    Reconciliación en sitio: la línea de PRODUCTO se reconoce por el FK `item` de
    la foto (identidad estable); las de VENTA se reusan por orden de aparición y
    sólo se crean/borran las sobrantes. Así los pk sobreviven y el documento no
    se reconstruye de cero en cada guardado.
    """
    from apps.cotizaciones.models import CotizacionItem

    filas = list(cot.productos_version.all().order_by("orden", "pk"))
    if not filas:
        return
    existentes = list(cot.items.all().order_by("orden", "pk"))
    # Cola de líneas de venta reutilizables (las de producto tienen su FK).
    cola_ventas = [it for it in existentes if it.agrupado]
    conservados: set[int] = set()
    orden = 0

    for fila in filas:
        # 1) La línea del producto.
        item = fila.item if fila.item_id else None
        if item is None:
            item = CotizacionItem(cotizacion=cot)
        item.orden = orden
        item.servicio_id = fila.servicio_id
        item.variacion_id = fila.variacion_id
        item.concepto = _nombre_de(fila)[:150]
        item.descripcion = fila.nota or ""
        item.imagen_file_id = fila.imagen_file_id or ""
        item.cantidad = Decimal(str(fila.cantidad or 0))
        item.precio_unitario = fila.precio_unitario if fila.precio_unitario is not None else CERO
        item.agrupado = False
        item.save()
        conservados.add(item.pk)
        if fila.item_id != item.pk:
            fila.item = item
            fila.save(update_fields=["item"])
        orden += 1

        # 2) Sus líneas de venta (se cobran aparte, se imprimen dentro de su
        #    bloque — ver `CotizacionItem.agrupado`).
        for venta in (fila.ventas_json or []):
            if not isinstance(venta, dict):
                continue
            desc = (venta.get("descripcion") or "").strip()
            precio = _a_decimal(venta.get("precio"))
            if not desc and precio == CERO:
                continue
            linea = cola_ventas.pop(0) if cola_ventas else CotizacionItem(cotizacion=cot)
            linea.orden = orden
            linea.servicio = None
            linea.variacion = None
            linea.concepto = desc[:150]
            linea.descripcion = ""
            linea.imagen_file_id = ""
            linea.cantidad = Decimal(str(max(1, int(venta.get("cantidad") or 1))))
            linea.precio_unitario = precio
            linea.agrupado = True
            linea.save()
            conservados.add(linea.pk)
            orden += 1

    # 3) Lo que ya no corresponde a ninguna fila de la foto se va.
    for it in existentes:
        if it.pk not in conservados:
            it.delete()


def _a_decimal(valor) -> Decimal:
    from decimal import InvalidOperation
    try:
        return Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return CERO


def _a_decimal_opcional(valor) -> Decimal | None:
    """Como `_a_decimal`, pero **conserva el None**: en una escala de volumen un
    nulo significa «hereda de la Opción A», no cero."""
    if valor is None or str(valor).strip() == "":
        return None
    return _a_decimal(valor)


# ── Restaurar la versión en edición ──────────────────────────────────────────

def _indice_lineas(proyecto):
    """Índice de las líneas vivas para emparejar con la foto.

    Por NOMBRE primero (el alias es lo que distingue dos usos del mismo producto
    del catálogo — lección de S-Ajustes-Jul29) y, si el par producto+variación se
    usa una sola vez, también por ahí.
    """
    por_nombre: dict[str, list] = {}
    por_srv: dict[tuple, list] = {}
    for pp in proyecto.productos.all():
        por_nombre.setdefault(pp.nombre_visible.strip().lower(), []).append(pp)
        por_srv.setdefault((pp.servicio_id, pp.variacion_id), []).append(pp)
    return por_nombre, por_srv


def restaurar_en_edicion(cot, actor=None) -> dict:
    """Repone en las líneas vivas los valores de esta versión.

    **No borra** lo que el proyecto tenga y la versión no traiga: una línea puede
    tener un egreso ya registrado en Tesorería, y hacerla desaparecer dejaría el
    gasto colgando. Lo que no estaba en la versión se queda como está.
    """
    import json as _json

    from .models import ProyectoProducto
    from .services_procesos import (
        sincronizar_escalas,
        sincronizar_procesos,
        sincronizar_ventas,
    )

    proyecto = cot.proyecto
    filas = list(cot.productos_version.all().order_by("orden", "pk"))
    if proyecto is None or not filas:
        return {"actualizadas": 0, "creadas": 0}

    por_nombre, por_srv = _indice_lineas(proyecto)
    usadas: set[int] = set()

    def _tomar(cola):
        for pp in cola:
            if pp.pk not in usadas:
                usadas.add(pp.pk)
                return pp
        return None

    actualizadas = creadas = 0
    with transaction.atomic():
        for orden, fila in enumerate(filas):
            pp = _tomar(por_nombre.get(_nombre_de(fila).strip().lower(), []))
            if pp is None:
                cola = por_srv.get((fila.servicio_id, fila.variacion_id), [])
                pp = _tomar(cola) if len(cola) == 1 else None
            if pp is None:
                if not fila.servicio_id:
                    continue  # sin producto del catálogo no hay línea que crear
                pp = ProyectoProducto(proyecto=proyecto, servicio_id=fila.servicio_id)
                creadas += 1
            else:
                actualizadas += 1
            pp.variacion_id = fila.variacion_id
            pp.proveedor_id = fila.proveedor_id
            pp.nombre_proyecto = fila.nombre_proyecto or ""
            pp.cantidad = fila.cantidad or 1
            pp.merma = fila.merma or 0
            pp.precio_unitario = fila.precio_unitario
            pp.costo_unitario = fila.costo_unitario
            pp.costo_unitario_expr = fila.costo_unitario_expr or ""
            pp.nota = fila.nota or ""
            pp.incluir_en_calculo = True
            pp.visible_pdf = bool(getattr(fila, "visible_pdf", True))
            pp.orden = orden
            pp.save()
            sincronizar_procesos(pp, _json.dumps(fila.procesos_json or []))
            sincronizar_ventas(pp, _json.dumps(fila.ventas_json or []))
            sincronizar_escalas(pp, _json.dumps(fila.escalas_json or []))
        proyecto.recalcular_monto_estimado()
    return {"actualizadas": actualizadas, "creadas": creadas}


# ── Para pintar la pestaña ───────────────────────────────────────────────────

class _Proceso:
    """Objeto mínimo con la forma que espera la tarjeta (`f.proc_impresion`,
    `f.procs_operativos`). Los procesos de una foto viven en JSON, no en filas."""

    def __init__(self, fila: dict, proveedores: dict):
        self.tipo = fila.get("tipo") or "operativo"
        self.proveedor_id = fila.get("proveedor_id")
        self.proveedor = proveedores.get(self.proveedor_id)
        self.descripcion = fila.get("descripcion") or ""
        self.costo = _a_decimal(fila.get("costo"))
        self.costo_expr = fila.get("costo_expr") or ""
        self.por_pieza = bool(fila.get("por_pieza"))


class _Escala:
    """Escala de volumen de una foto, con la forma que espera la tarjeta.

    Conserva los nulos (heredar de la Opción A) y expone `letra` como el modelo.
    """

    def __init__(self, fila: dict, orden: int):
        self.orden = orden
        self.cantidad = max(1, int(fila.get("cantidad") or 1))
        self.merma = max(0, int(fila.get("merma") or 0))
        self.precio_unitario = _a_decimal_opcional(fila.get("precio_unitario"))
        self.costo_unitario = _a_decimal_opcional(fila.get("costo_unitario"))
        self.costo_unitario_expr = fila.get("costo_unitario_expr") or ""
        self.impresion_costo = _a_decimal_opcional(fila.get("impresion_costo"))
        self.impresion_costo_expr = fila.get("impresion_costo_expr") or ""
        self.impresion_por_pieza = bool(fila.get("impresion_por_pieza"))
        self.extras_json = list(fila.get("extras") or [])
        self.activa = bool(fila.get("activa"))
        self.visible_pdf = bool(fila.get("visible_pdf", True))

    @property
    def letra(self) -> str:
        return chr(ord("B") + min(self.orden, 24))

    def extras(self) -> list[dict]:
        return [e for e in self.extras_json if isinstance(e, dict)]


class _Venta:
    def __init__(self, fila: dict):
        self.descripcion = fila.get("descripcion") or ""
        self.cantidad = max(1, int(fila.get("cantidad") or 1))
        self.precio_unitario = _a_decimal(fila.get("precio"))


def anotar_procesos(formset) -> None:
    """Anota en cada form de la foto lo que la tarjeta espera, leyendo el JSON."""
    from apps.el_catalogo.models import Proveedor

    ids = set()
    for form in formset.forms:
        for p in (getattr(form.instance, "procesos_json", None) or []):
            if isinstance(p, dict) and p.get("proveedor_id"):
                ids.add(p["proveedor_id"])
    proveedores = {p.pk: p for p in Proveedor.objects.filter(pk__in=ids)} if ids else {}

    for form in formset.forms:
        inst = form.instance
        impresion, operativos = None, []
        for cruda in (inst.procesos_json or []):
            if not isinstance(cruda, dict):
                continue
            proc = _Proceso(cruda, proveedores)
            if proc.tipo == "impresion" and impresion is None:
                impresion = proc
            elif proc.tipo == "operativo":
                operativos.append(proc)
        form.proc_impresion = impresion
        form.procs_operativos = operativos
        form.procs_venta = [_Venta(v) for v in (inst.ventas_json or [])
                            if isinstance(v, dict)]
        form.escalas = [
            _Escala(e, i) for i, e in enumerate(
                [x for x in (inst.escalas_json or []) if isinstance(x, dict)])
        ]
        form.escala_activa = next((e for e in form.escalas if e.activa), None)
