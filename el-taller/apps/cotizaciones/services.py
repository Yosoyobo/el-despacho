"""Services de Las Cotizaciones.

Cubre transiciones de estado y emisión de eventos Portavoz.
Los cálculos viven en `Cotizacion.calcular_totales` para que el detalle
sea consultable sin importar este módulo.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Cotizacion


def _emitir(tipo: str, cot: Cotizacion, actor, payload_extra: dict | None = None):
    payload = {
        "cotizacion_id": cot.id,
        "codigo": cot.codigo,
        "cliente_id": cot.cliente_id,
        "estado": cot.estado,
    }
    if payload_extra:
        payload.update(payload_extra)
    emitir(EventoPortavoz(
        tipo=tipo,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload=payload,
    ))


def emitir_creada(cot: Cotizacion, actor):
    _emitir("cotizacion.creada", cot, actor, {"titulo": cot.titulo})


def emitir_actualizada(cot: Cotizacion, actor):
    _emitir("cotizacion.actualizada", cot, actor)


def marcar_enviada(cot: Cotizacion, actor, email_destino: str = "") -> Cotizacion:
    if cot.estado != "borrador":
        raise ValueError("Solo se puede enviar una cotización en borrador.")
    with transaction.atomic():
        cot.estado = "enviada"
        cot.enviada_en = timezone.now()
        cot.enviada_a_email = email_destino or cot.enviada_a_email or (
            getattr(cot.cliente, "email_contacto", "") or ""
        )
        cot.save(update_fields=["estado", "enviada_en", "enviada_a_email", "actualizado_en"])
    _emitir("cotizacion.enviada", cot, actor, {"email_destino": cot.enviada_a_email})
    return cot


def marcar_aprobada(cot: Cotizacion, actor, nombre: str, email: str = "",
                    referencia: str = "") -> Cotizacion:
    if cot.estado != "enviada":
        raise ValueError("Solo se puede aprobar una cotización enviada.")
    if not nombre.strip():
        raise ValueError("Debe registrarse el nombre de quien aprobó.")
    with transaction.atomic():
        cot.estado = "aprobada"
        cot.aprobada_en = timezone.now()
        cot.aprobada_por_nombre = nombre.strip()
        cot.aprobada_por_email = email.strip()
        cot.referencia_aprobacion = referencia.strip()
        cot.save(update_fields=[
            "estado", "aprobada_en", "aprobada_por_nombre",
            "aprobada_por_email", "referencia_aprobacion", "actualizado_en",
        ])
    _emitir("cotizacion.aprobada", cot, actor, {
        "aprobada_por": cot.aprobada_por_nombre,
    })
    return cot


def marcar_rechazada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    if cot.estado != "enviada":
        raise ValueError("Solo se puede rechazar una cotización enviada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de rechazo.")
    with transaction.atomic():
        cot.estado = "rechazada"
        cot.rechazada_en = timezone.now()
        cot.motivo_rechazo = motivo
        cot.save(update_fields=["estado", "rechazada_en", "motivo_rechazo", "actualizado_en"])
    _emitir("cotizacion.rechazada", cot, actor, {"motivo": motivo[:200]})
    return cot


def marcar_anulada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    if cot.estado == "anulada":
        raise ValueError("La cotización ya estaba anulada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de anulación.")
    with transaction.atomic():
        cot.estado = "anulada"
        cot.anulada_en = timezone.now()
        cot.anulada_por = actor if getattr(actor, "is_authenticated", False) else None
        cot.motivo_anulacion = motivo[:300]
        cot.save(update_fields=[
            "estado", "anulada_en", "anulada_por", "motivo_anulacion", "actualizado_en",
        ])
    _emitir("cotizacion.anulada", cot, actor, {"motivo": motivo[:200]})
    return cot


def duplicar(cot: Cotizacion, actor) -> Cotizacion:
    """Crea una copia en estado borrador con los mismos items e impuestos."""
    from .models import CotizacionImpuesto, CotizacionItem
    with transaction.atomic():
        nueva = Cotizacion.objects.create(
            cliente=cot.cliente,
            proyecto=cot.proyecto,
            titulo=f"Copia de {cot.titulo}"[:200],
            estado="borrador",
            moneda=cot.moneda,
            descuento_global_porcentaje=cot.descuento_global_porcentaje,
            notas=cot.notas,
            terminos=cot.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in cot.items.all():
            CotizacionItem.objects.create(
                cotizacion=nueva,
                orden=it.orden,
                servicio=it.servicio,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for ci in cot.impuestos.all():
            CotizacionImpuesto.objects.create(cotizacion=nueva, tasa=ci.tasa)
    emitir_creada(nueva, actor)
    return nueva


# --- KPIs ----------------------------------------------------------------

def kpis_landing() -> dict:
    """Conteos para el header de la lista de Cotizaciones."""
    qs = Cotizacion.objects.exclude(estado="anulada")
    from datetime import date
    return {
        "borradores": qs.filter(estado="borrador").count(),
        "enviadas": qs.filter(estado="enviada").count(),
        "aprobadas": qs.filter(estado="aprobada").count(),
        "vencidas": qs.filter(
            estado="enviada", fecha_validez__lt=date.today()
        ).count(),
    }
