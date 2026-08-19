"""Duplicar proyecto (LC 2026-07).

Clona un proyecto COMPLETO con un nombre nuevo: cliente, fechas, régimen fiscal
y los productos involucrados **tal como se ven** — su nombre en el proyecto, su
descripción, proveedores, costos, precios, merma, orden, las opciones de volumen,
los procesos de producción y lo que se le cobra al cliente aparte.

**Exclusiones duras** (no se duplican flujos de dinero históricos): cotizaciones,
facturas, egresos/ingresos, montos facturado/cobrado, asignaciones de egreso, y
los sellos de estado (arranca en el primer estado del ciclo, por_cotizar).
"""

from __future__ import annotations

from django.db import transaction

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Proyecto, ProyectoProducto, ProyectoProductoEscala
from .models.proceso import ProyectoProductoProceso
from .models.venta import ProyectoProductoVenta


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
    for pp in origen.productos.all().prefetch_related("procesos", "escalas", "ventas"):
        nueva_linea = ProyectoProducto.objects.create(
            proyecto=nuevo,
            servicio_id=pp.servicio_id,
            variacion_id=pp.variacion_id,
            proveedor_id=pp.proveedor_id,
            # LC 2026-08-18: el ALIAS del producto en este proyecto. Sin él, la
            # copia perdía el nombre que ve el cliente («TShirt Modelo Janet»
            # volvía a ser el del catálogo) y con él la especificación que el
            # documento arma a partir del nombre. Igual el `orden`: la copia
            # tiene que verse en el mismo orden que el original.
            nombre_proyecto=pp.nombre_proyecto,
            orden=pp.orden,
            # LC 2026-08-18 (Oscar): «las fotos de productos van ligadas a su
            # alias o nombre y sí viajan al duplicar». Se copia la REFERENCIA al
            # archivo de Drive, no el archivo: las dos líneas apuntan al mismo, y
            # quitarla de una sólo desliga (el archivo nunca se borra de Drive,
            # ver `forms._desligar_imagen`). Una línea sin alias no tiene foto
            # propia —la suya vive en el catálogo—, así que ahí esto no hace nada.
            imagen_file_id=pp.imagen_file_id,
            imagen_url=pp.imagen_url,
            cantidad=pp.cantidad,
            precio_unitario=pp.precio_unitario,
            costo_unitario=pp.costo_unitario,
            # Las cuentas escritas viajan con sus montos: si el costo se capturó
            # como «35+15+15», la copia también lo dice (LC 2026-08-18; el par del
            # precio nació en ese mismo sprint).
            precio_unitario_expr=pp.precio_unitario_expr,
            costo_unitario_expr=pp.costo_unitario_expr,
            merma=pp.merma,
            incluir_en_calculo=pp.incluir_en_calculo,
            visible_pdf=pp.visible_pdf,
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
                costo_expr=proc.costo_expr,
                por_pieza=proc.por_pieza,
            )
        # LC 2026-08-18: lo que se le COBRA al cliente aparte del producto
        # (Ponchado, arte…). No se copiaba, así que la copia salía más barata que
        # el original —sin que nada lo avisara— y la cotización nueva perdía esas
        # líneas. Son cobros, no gastos: no tienen nada que ver con las
        # exclusiones de dinero histórico de arriba.
        for venta in pp.ventas.all():
            ProyectoProductoVenta.objects.create(
                producto=nueva_linea, orden=venta.orden,
                descripcion=venta.descripcion, cantidad=venta.cantidad,
                precio_unitario=venta.precio_unitario,
                precio_expr=venta.precio_expr,
            )
        # LC 2026-08-17: las escalas de volumen viajan con la línea.
        for esc in pp.escalas.all():
            ProyectoProductoEscala.objects.create(
                producto=nueva_linea, orden=esc.orden, cantidad=esc.cantidad,
                merma=esc.merma, precio_unitario=esc.precio_unitario,
                precio_unitario_expr=esc.precio_unitario_expr,
                costo_unitario=esc.costo_unitario,
                costo_unitario_expr=esc.costo_unitario_expr,
                impresion_costo=esc.impresion_costo,
                impresion_costo_expr=esc.impresion_costo_expr,
                impresion_por_pieza=esc.impresion_por_pieza,
                extras_json=list(esc.extras_json or []),
                activa=esc.activa, visible_pdf=esc.visible_pdf,
            )
    emitir(EventoPortavoz(
        tipo="proyecto.duplicado",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={"origen_id": origen.pk, "nuevo_id": nuevo.pk, "codigo": nuevo.codigo},
    ))
    return nuevo
