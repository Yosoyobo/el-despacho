"""Gastos del proyecto ↔ Egresos de Tesorería — contabilidad en línea.

Decisión (Oscar, 2026-06-12): cada gasto del proyecto se liga POR SEPARADO a
un Egreso registrado. Unidades de gasto:

- **producto**: una línea `ProyectoProducto` incluida → monto = `costo_total_linea`
  (producto + merma, SIN procesos), proveedor = el de la línea.
- **impresion**: un `Proceso` tipo impresión → monto = su costo, proveedor del proceso.
- **operativo**: un `Proceso` tipo operativo (clavos, pegamento…) → monto = su
  costo, sin proveedor.

Un gasto está **registrado** si tiene un Egreso vigente (no anulado). Los que no,
salen como alerta en el proyecto y como "gastos no registrados" en Tesorería,
con un botón para registrarlos (crea el Egreso y lo liga).
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)

CENTRO_SLUG = "insumos-de-proyecto"
CERO = Decimal("0.00")

# S-LC-Feedback-V8 (Oscar): la alerta de gastos sin registrar solo aplica de
# "En proceso de diseño" en adelante (antes de eso el proyecto aún se cotiza).
ESTADOS_CON_GASTOS = {
    "en_proceso_diseno", "en_proceso_produccion", "entregado", "cerrado",
}

# LC 2026-07 (Oscar): el recuadro de egresos sale en TODOS los estados, pero la
# alerta de "pagos pendientes sin registrar" solo de PRODUCCIÓN en adelante.
ESTADOS_ALERTA_PAGOS = {"en_proceso_produccion", "entregado", "cerrado"}


def debe_mostrar_gastos(proyecto) -> bool:
    return getattr(proyecto, "estado", None) in ESTADOS_CON_GASTOS


def debe_mostrar_alerta_pagos(proyecto) -> bool:
    return getattr(proyecto, "estado", None) in ESTADOS_ALERTA_PAGOS


def desglose_iva(proyecto, pendientes: list[dict]) -> dict:
    """Subtotal + IVA = total de los gastos pendientes (S-LC-Feedback-V8).

    El monto de cada unidad es el costo SIN IVA (es lo que cuesta producir);
    el IVA que paga la empresa se calcula con la tasa efectiva del proyecto.
    """
    subtotal = sum((u["monto"] for u in pendientes), CERO)
    try:
        tasa = Decimal(str(proyecto.iva_tasa_efectiva))
    except Exception:  # noqa: BLE001
        tasa = Decimal("0.16")
    iva = (subtotal * tasa).quantize(Decimal("0.01"))
    return {
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "iva": iva,
        "total": (subtotal + iva).quantize(Decimal("0.01")),
        "iva_label": f"{float(tasa * 100):g}%",
    }


def _registrado(egreso) -> bool:
    return egreso is not None and not egreso.anulado


def _pagado(egreso) -> bool:
    """Un gasto está PAGADO cuando su egreso vigente ya se saldó o quedó por
    reembolsar (LC 2026-07: solo se registra un egreso al realizarse). Un egreso
    'pendiente' (cuenta por pagar auto-generada) todavía cuenta como pendiente."""
    return (
        egreso is not None
        and not egreso.anulado
        and egreso.estado_pago in ("pagado", "por_reembolsar")
    )


def _nombre_base(pp) -> str:
    return pp.variacion.nombre if pp.variacion_id else pp.servicio.nombre


def _label_produccion(pp) -> str:
    """Etiqueta del gasto del producto que refleja las piezas a PRODUCIR
    (cantidad + merma), no solo la cantidad vendida. Reporte Oscar: el gasto
    decía '35x' cuando se producen 45 (35 + 10 merma)."""
    base = _nombre_base(pp)
    piezas = pp.cantidad + pp.merma
    if pp.merma:
        return f"{base} · {piezas} pz ({pp.cantidad} + {pp.merma} merma)"
    return f"{base} · {piezas} pz"


def _monto_proceso(proc, pp) -> Decimal:
    """Costo del proceso: fijo o × piezas producidas según `por_pieza`."""
    c = Decimal(str(proc.costo or 0))
    if proc.por_pieza:
        c = c * (pp.cantidad + pp.merma)
    return c.quantize(Decimal("0.01"))


def _label_proceso(proc, pp) -> str:
    piezas = pp.cantidad + pp.merma
    suf = f" (× {piezas} pz)" if proc.por_pieza else ""
    return f"{_nombre_base(pp)} · {proc.etiqueta}{suf}"


def iter_unidades(proyecto):
    """Genera dicts de unidad de gasto del proyecto (solo con monto > 0)."""
    lineas = (
        proyecto.productos
        .filter(incluir_en_calculo=True)
        .select_related("proveedor", "servicio", "variacion", "egreso")
        .prefetch_related("procesos", "procesos__proveedor", "procesos__egreso")
    )
    for pp in lineas:
        monto = Decimal(str(pp.costo_total_linea)).quantize(Decimal("0.01"))
        if monto > 0:
            yield {
                "clase": "producto", "pk": pp.pk, "tipo": "producto",
                "label": _label_produccion(pp), "monto": monto,
                "proveedor": pp.proveedor, "egreso": pp.egreso,
                "registrado": _registrado(pp.egreso),
                "pagado": _pagado(pp.egreso),
            }
        for proc in pp.procesos.all():
            c = _monto_proceso(proc, pp)
            if c <= 0:
                continue
            yield {
                "clase": "proceso", "pk": proc.pk, "tipo": proc.tipo,
                "label": _label_proceso(proc, pp), "monto": c,
                "proveedor": proc.proveedor if proc.tipo == "impresion" else None,
                "egreso": proc.egreso,
                "registrado": _registrado(proc.egreso),
                "pagado": _pagado(proc.egreso),
            }


def pendientes_de(proyecto) -> list[dict]:
    """Unidades de gasto del proyecto SIN egreso vigente (para la vista global
    de Tesorería «Gastos no registrados» y la auto-generación)."""
    return [u for u in iter_unidades(proyecto) if not u["registrado"]]


def pagos_pendientes_de(proyecto) -> list[dict]:
    """Unidades de gasto cuyo PAGO aún no se registra: sin egreso, egreso
    anulado, o egreso todavía en «Pendiente» (cuenta por pagar auto-generada).
    Alimenta la alerta del detalle del proyecto (LC 2026-07)."""
    return [u for u in iter_unidades(proyecto) if not u["pagado"]]


def _obj_de(proyecto, clase: str, pk: int):
    from .models import ProyectoProducto, ProyectoProductoProceso
    if clase == "producto":
        return ProyectoProducto.objects.filter(proyecto=proyecto, pk=pk).first()
    if clase == "proceso":
        return ProyectoProductoProceso.objects.filter(producto__proyecto=proyecto, pk=pk).first()
    return None


def _datos_egreso(proyecto, clase: str, obj):
    """(monto, proveedor, proveedor_nombre, descripcion) para el egreso."""
    if clase == "producto":
        monto = Decimal(str(obj.costo_total_linea)).quantize(Decimal("0.01"))
        proveedor = obj.proveedor
        etiqueta = _label_produccion(obj)
    else:  # proceso
        monto = _monto_proceso(obj, obj.producto)
        proveedor = obj.proveedor if obj.tipo == "impresion" else None
        etiqueta = _label_proceso(obj, obj.producto)
    proveedor_nombre = (proveedor.razon_social if proveedor else "Gasto de proyecto")[:200]
    descripcion = f"Proyecto {proyecto.codigo} · {etiqueta}"[:300]
    return monto, proveedor, proveedor_nombre, descripcion


def datos_para_modal(proyecto, clase: str, pk: int):
    """Info de la unidad de gasto para precargar el modal 'Registrar'.
    Devuelve `{monto, label, proveedor, ya_registrado}` o None."""
    obj = _obj_de(proyecto, clase, pk)
    if obj is None:
        return None
    monto, proveedor, proveedor_nombre, descripcion = _datos_egreso(proyecto, clase, obj)
    eg = obj.egreso
    pendiente = eg is not None and not eg.anulado and eg.estado_pago == "pendiente"
    return {
        "monto": monto, "label": getattr(obj, "etiqueta", descripcion),
        "proveedor": proveedor, "proveedor_nombre": proveedor_nombre,
        "ya_registrado": _registrado(obj.egreso),
        "pagado": _pagado(obj.egreso),
        "egreso": eg,
        "pendiente": pendiente,
    }


def registrar_egreso(proyecto, clase: str, pk: int, *, actor=None,
                     centro=None, metodo="transferencia", estado_pago="pendiente",
                     pagado_por=None, solicitado_por=None, proveedor=None, fecha=None):
    """Crea el Egreso de una unidad de gasto y lo liga. Idempotente (si ya
    tiene egreso vigente, lo devuelve). Devuelve el Egreso o None si no se
    pudo (catálogo incompleto / objeto inexistente / monto 0).

    Los parámetros opcionales (centro, metodo, estado_pago, pagado_por,
    solicitado_por, proveedor) vienen del modal "Registrar" (S-LC-Feedback-V8 /
    V2). Sin ellos usa los defaults (centro `insumos-de-proyecto`,
    transferencia, pendiente, proveedor derivado del gasto). `proveedor`
    permite elegir/corregir el proveedor desde el modal."""
    from apps.tesoreria.models import CentroDeCosto, Egreso

    obj = _obj_de(proyecto, clase, pk)
    if obj is None:
        return None
    if _registrado(obj.egreso):
        return obj.egreso

    monto, proveedor_def, proveedor_nombre, descripcion = _datos_egreso(proyecto, clase, obj)
    if proveedor is not None:
        proveedor_def = proveedor
        proveedor_nombre = (proveedor.razon_social or proveedor_nombre)[:200]
    proveedor = proveedor_def
    if monto <= 0:
        return None
    if centro is None:
        centro = CentroDeCosto.objects.filter(slug=CENTRO_SLUG).first()
    if centro is None:
        logger.warning("proyecto=%s: centro '%s' ausente — no se registra el gasto.",
                       proyecto.pk, CENTRO_SLUG)
        return None

    with transaction.atomic():
        egreso = Egreso.objects.create(
            monto=monto, fecha=fecha or date.today(), descripcion=descripcion,
            proveedor=proveedor, proveedor_nombre=proveedor_nombre,
            centro_de_costo=centro, proyecto=proyecto,
            estado_pago=estado_pago or "pendiente", metodo=metodo or "transferencia",
            pagado_por=pagado_por, solicitado_por=solicitado_por, origen="proyecto",
        )
        obj.egreso = egreso
        obj.save(update_fields=["egreso"])

    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="proyecto.gasto_registrado",
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo,
                     "clase": clase, "monto": float(monto), "egreso_codigo": egreso.codigo},
        ))
    return egreso


def registrar_pendientes(proyecto, *, actor=None) -> list:
    """Registra TODOS los gastos pendientes del proyecto. Devuelve los egresos
    creados. Usado por el botón 'registrar todos' y por el signal de producción."""
    creados = []
    for u in pendientes_de(proyecto):
        eg = registrar_egreso(proyecto, u["clase"], u["pk"], actor=actor)
        if eg is not None:
            creados.append(eg)
    return creados


# ── Vista global para Tesorería ──────────────────────────────────────────

def proyectos_con_pendientes():
    """Lista [{proyecto, unidades, subtotal}] de proyectos no cancelados con
    gastos sin registrar. Para la página 'Gastos no registrados' de Tesorería."""
    from .models import Proyecto
    salida = []
    qs = (
        Proyecto.objects.filter(estado__in=ESTADOS_CON_GASTOS)
        .prefetch_related("productos", "productos__procesos")
    )
    for proyecto in qs:
        pend = pendientes_de(proyecto)
        if pend:
            subtotal = sum((u["monto"] for u in pend), CERO)
            salida.append({"proyecto": proyecto, "unidades": pend, "subtotal": subtotal})
    salida.sort(key=lambda d: d["subtotal"], reverse=True)
    return salida


def conteo_no_registrados() -> dict:
    """{cantidad, total} de gastos no registrados (para el KPI de Tesorería)."""
    cantidad = 0
    total = CERO
    for grupo in proyectos_con_pendientes():
        cantidad += len(grupo["unidades"])
        total += grupo["subtotal"]
    return {"cantidad": cantidad, "total": total.quantize(Decimal("0.01"))}
