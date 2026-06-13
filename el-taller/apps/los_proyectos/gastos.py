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


def debe_mostrar_gastos(proyecto) -> bool:
    return getattr(proyecto, "estado", None) in ESTADOS_CON_GASTOS


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
                "label": pp.etiqueta, "monto": monto,
                "proveedor": pp.proveedor, "egreso": pp.egreso,
                "registrado": _registrado(pp.egreso),
            }
        for proc in pp.procesos.all():
            c = Decimal(str(proc.costo or 0)).quantize(Decimal("0.01"))
            if c <= 0:
                continue
            yield {
                "clase": "proceso", "pk": proc.pk, "tipo": proc.tipo,
                "label": f"{pp.etiqueta} · {proc.etiqueta}", "monto": c,
                "proveedor": proc.proveedor if proc.tipo == "impresion" else None,
                "egreso": proc.egreso,
                "registrado": _registrado(proc.egreso),
            }


def pendientes_de(proyecto) -> list[dict]:
    """Unidades de gasto del proyecto SIN egreso vigente."""
    return [u for u in iter_unidades(proyecto) if not u["registrado"]]


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
        etiqueta = obj.etiqueta
    else:  # proceso
        monto = Decimal(str(obj.costo or 0)).quantize(Decimal("0.01"))
        proveedor = obj.proveedor if obj.tipo == "impresion" else None
        etiqueta = obj.etiqueta
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
    return {
        "monto": monto, "label": getattr(obj, "etiqueta", descripcion),
        "proveedor": proveedor, "proveedor_nombre": proveedor_nombre,
        "ya_registrado": _registrado(obj.egreso),
    }


def registrar_egreso(proyecto, clase: str, pk: int, *, actor=None,
                     centro=None, metodo="transferencia", estado_pago="pendiente",
                     pagado_por=None, solicitado_por=None):
    """Crea el Egreso de una unidad de gasto y lo liga. Idempotente (si ya
    tiene egreso vigente, lo devuelve). Devuelve el Egreso o None si no se
    pudo (catálogo incompleto / objeto inexistente / monto 0).

    Los parámetros opcionales (centro, metodo, estado_pago, pagado_por,
    solicitado_por) vienen del modal "Registrar" (S-LC-Feedback-V8). Sin ellos
    usa los defaults (centro `insumos-de-proyecto`, transferencia, pendiente)."""
    from apps.tesoreria.models import CentroDeCosto, Egreso

    obj = _obj_de(proyecto, clase, pk)
    if obj is None:
        return None
    if _registrado(obj.egreso):
        return obj.egreso

    monto, proveedor, proveedor_nombre, descripcion = _datos_egreso(proyecto, clase, obj)
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
            monto=monto, fecha=date.today(), descripcion=descripcion,
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
