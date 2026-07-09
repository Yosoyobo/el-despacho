"""Duplicar proyecto (LC 2026-07).

Clona un proyecto COMPLETO con un nombre nuevo: cliente, fechas, régimen fiscal
y los productos involucrados (con proveedores, costos, precios, merma y procesos).

**Exclusiones duras** (no se duplican flujos de dinero históricos): cotizaciones,
facturas, egresos/ingresos, montos facturado/cobrado, asignaciones de egreso, y
los sellos de estado (arranca en el primer estado del ciclo, por_cotizar).
"""

from __future__ import annotations

from django.db import transaction

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Proyecto, ProyectoProducto
from .models.proceso import ProyectoProductoProceso


@transaction.atomic
def duplicar_proyecto(origen: Proyecto, *, nombre: str, actor) -> Proyecto:
    """Crea y devuelve el proyecto duplicado. `nombre` es obligatorio."""
    nombre = (nombre or "").strip() or f"Copia de {origen.nombre}"
    nuevo = Proyecto.objects.create(
        nombre=nombre[:200],
        cliente=origen.cliente,
        descripcion=origen.descripcion,
        estado="por_cotizar",
        fecha_inicio=origen.fecha_inicio,
        fecha_compromiso=origen.fecha_compromiso,
        monto_estimado=origen.monto_estimado,
        regimen_fiscal=origen.regimen_fiscal,
        iva_exento=origen.iva_exento,
        creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        # Dinero NO se hereda: montos facturado/cobrado quedan en su default 0.
    )
    for pp in origen.productos.all().prefetch_related("procesos"):
        nueva_linea = ProyectoProducto.objects.create(
            proyecto=nuevo,
            servicio_id=pp.servicio_id,
            variacion_id=pp.variacion_id,
            proveedor_id=pp.proveedor_id,
            cantidad=pp.cantidad,
            precio_unitario=pp.precio_unitario,
            costo_unitario=pp.costo_unitario,
            merma=pp.merma,
            incluir_en_calculo=pp.incluir_en_calculo,
            nota=pp.nota,
            # egreso NO se hereda (marca de idempotencia de producción).
        )
        for proc in pp.procesos.all():
            ProyectoProductoProceso.objects.create(
                producto=nueva_linea,
                tipo=proc.tipo,
                orden=proc.orden,
                proveedor_id=proc.proveedor_id,
                descripcion=proc.descripcion,
                costo=proc.costo,
                por_pieza=proc.por_pieza,
            )
    emitir(EventoPortavoz(
        tipo="proyecto.duplicado",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={"origen_id": origen.pk, "nuevo_id": nuevo.pk, "codigo": nuevo.codigo},
    ))
    return nuevo
