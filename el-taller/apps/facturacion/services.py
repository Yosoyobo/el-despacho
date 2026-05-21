"""Services de La Facturación.

Transiciones de estado, integración con Tesorería (cobros) y emisión
de eventos Portavoz. Los asientos contables los genera `signals.py`
desde la app `contaduria` para mantener la dependencia unidireccional.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Factura, FacturaImpuesto, FacturaItem

CERO = Decimal("0.00")


def _emitir(tipo: str, fac: Factura, actor, payload_extra: dict | None = None):
    payload = {
        "factura_id": fac.id,
        "codigo": fac.codigo,
        "cliente_id": fac.cliente_id,
        "estado": fac.estado,
    }
    if payload_extra:
        payload.update(payload_extra)
    emitir(EventoPortavoz(
        tipo=tipo,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload=payload,
    ))


def emitir_creada(fac: Factura, actor):
    _emitir("factura.creada", fac, actor, {"titulo": fac.titulo})


def emitir_actualizada(fac: Factura, actor):
    _emitir("factura.actualizada", fac, actor)


def crear_desde_cotizacion(cotizacion, actor) -> Factura:
    """Clona items+impuestos+vínculo, hereda datos comerciales. Estado
    borrador. Vencimiento por default 30 días desde hoy."""
    with transaction.atomic():
        fac = Factura.objects.create(
            cliente=cotizacion.cliente,
            proyecto=cotizacion.proyecto,
            cotizacion_origen=cotizacion,
            titulo=cotizacion.titulo[:200],
            estado="borrador",
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=30),
            moneda=cotizacion.moneda,
            descuento_global_porcentaje=cotizacion.descuento_global_porcentaje,
            notas=cotizacion.notas,
            terminos=cotizacion.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in cotizacion.items.all():
            FacturaItem.objects.create(
                factura=fac,
                orden=it.orden,
                servicio=it.servicio,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for ci in cotizacion.impuestos.all():
            FacturaImpuesto.objects.create(factura=fac, tasa=ci.tasa)
    _emitir("factura.creada", fac, actor,
            {"titulo": fac.titulo, "cotizacion_id": cotizacion.id})
    return fac


def emitir_factura(fac: Factura, actor) -> Factura:
    """borrador → emitida. Dispara el asiento via signal post_save."""
    if fac.estado != "borrador":
        raise ValueError("Solo se puede emitir una factura en borrador.")
    with transaction.atomic():
        fac.estado = "emitida"
        fac.emitida_en = timezone.now()
        fac.emitida_por = actor if getattr(actor, "is_authenticated", False) else None
        fac.save(update_fields=["estado", "emitida_en", "emitida_por", "actualizado_en"])
    _emitir("factura.emitida", fac, actor)
    return fac


def registrar_cobro(
    fac: Factura,
    *,
    monto,
    fecha,
    metodo: str,
    actor,
    banco_o_caja: str = "banco",  # noqa: ARG001 (futuro: forzar slot caja vs banco)
):
    """Crea un `tesoreria.Ingreso` vinculado y recalcula `monto_cobrado`.
    Transiciona a cobrada_parcial / cobrada_total según corresponda.
    """
    if fac.estado not in {"emitida", "cobrada_parcial"}:
        raise ValueError("Solo se puede cobrar una factura emitida o parcialmente cobrada.")
    monto = Decimal(str(monto)).quantize(Decimal("0.01"))
    if monto <= 0:
        raise ValueError("El monto del cobro debe ser mayor a cero.")
    saldo = fac.saldo_pendiente
    if monto > saldo + Decimal("0.01"):
        raise ValueError(f"El monto del cobro ({monto}) excede el saldo pendiente ({saldo}).")

    from apps.tesoreria.models import Ingreso

    with transaction.atomic():
        Ingreso.objects.create(
            factura=fac,
            monto=monto,
            fecha=fecha,
            metodo=metodo,
            descripcion=f"Cobro de {fac.codigo}",
            cliente=fac.cliente,
            proyecto=fac.proyecto,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        recalcular_monto_cobrado(fac)
        total = fac.calcular_totales()["total"]
        if fac.monto_cobrado + Decimal("0.01") >= total:
            fac.estado = "cobrada_total"
        elif fac.monto_cobrado > 0:
            fac.estado = "cobrada_parcial"
        fac.save(update_fields=["estado", "monto_cobrado", "actualizado_en"])

    if fac.estado == "cobrada_total":
        _emitir("factura.cobrada_total", fac, actor, {"monto": float(monto)})
    else:
        _emitir("factura.cobrada_parcial", fac, actor, {"monto": float(monto)})
    return fac


def recalcular_monto_cobrado(fac: Factura) -> Decimal:
    """Recalcula monto_cobrado sumando Ingresos vigentes vinculados."""
    from apps.tesoreria.models import Ingreso
    total = Ingreso.vigentes.filter(factura=fac).aggregate(s=Sum("monto"))["s"] or CERO
    fac.monto_cobrado = Decimal(str(total)).quantize(Decimal("0.01"))
    return fac.monto_cobrado


def cancelar(fac: Factura, actor, motivo: str) -> Factura:
    if fac.estado == "cancelada":
        raise ValueError("La factura ya estaba cancelada.")
    if (fac.monto_cobrado or CERO) > 0:
        raise ValueError("Anula primero los cobros antes de cancelar la factura.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de cancelación.")
    with transaction.atomic():
        fac.estado = "cancelada"
        fac.cancelada_en = timezone.now()
        fac.cancelada_por = actor if getattr(actor, "is_authenticated", False) else None
        fac.motivo_cancelacion = motivo[:300]
        fac.save(update_fields=[
            "estado", "cancelada_en", "cancelada_por", "motivo_cancelacion",
            "actualizado_en",
        ])
    _emitir("factura.cancelada", fac, actor, {"motivo": motivo[:200]})
    return fac


def duplicar(fac: Factura, actor) -> Factura:
    """Crea copia en borrador con los mismos items e impuestos."""
    with transaction.atomic():
        nueva = Factura.objects.create(
            cliente=fac.cliente,
            proyecto=fac.proyecto,
            titulo=f"Copia de {fac.titulo}"[:200],
            estado="borrador",
            moneda=fac.moneda,
            descuento_global_porcentaje=fac.descuento_global_porcentaje,
            notas=fac.notas,
            terminos=fac.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in fac.items.all():
            FacturaItem.objects.create(
                factura=nueva,
                orden=it.orden,
                servicio=it.servicio,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for fi in fac.impuestos.all():
            FacturaImpuesto.objects.create(factura=nueva, tasa=fi.tasa)
    _emitir("factura.creada", nueva, actor, {"titulo": nueva.titulo})
    return nueva


# --- KPIs ----------------------------------------------------------------

def kpis_landing() -> dict:
    qs = Factura.objects.exclude(estado="cancelada")
    from datetime import date as _d
    hoy = _d.today()
    inicio_mes = hoy.replace(day=1)
    borradores = qs.filter(estado="borrador").count()
    emitidas = qs.filter(estado__in=["emitida", "cobrada_parcial"]).count()
    # 'vencidas' lo computamos en Python por simplicidad (saldo > 0 + fecha
    # vencimiento < hoy). Para listas grandes habría que mover a queryset.
    vencidas = 0
    for f in qs.filter(estado__in=["emitida", "cobrada_parcial"], fecha_vencimiento__lt=hoy):
        if f.saldo_pendiente > 0:
            vencidas += 1
    cobradas_mes = qs.filter(
        estado="cobrada_total", emitida_en__gte=inicio_mes,
    ).count()
    return {
        "borradores": borradores,
        "emitidas": emitidas,
        "vencidas": vencidas,
        "cobradas_mes": cobradas_mes,
    }
