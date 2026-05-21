"""Signals de La Facturación: generan asientos contables al emitir/cancelar.

Patrón espejo de `apps/contaduria/signals.py`:
- post_save Factura: si transiciona a estado='emitida' → asiento auto_factura_emitida.
- post_save Factura: si transiciona a estado='cancelada' → reverso.
- Idempotente vía `referencia_externa`.
- Silent skip si catálogo de cuentas incompleto.
- transaction.on_commit para no acoplar al rollback de tx fallida.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

log = logging.getLogger("despacho.facturacion")

CERO = Decimal("0.00")


def _ref_emitida(pk: int) -> str:
    return f"facturacion.factura:{pk}"


def _ref_cancelada(pk: int) -> str:
    return f"facturacion.factura.cancelacion:{pk}"


# Cache de estado previo (pre_save → post_save), por PK.
_estado_previo: dict[int, str] = {}


@receiver(pre_save, sender="facturacion.Factura", dispatch_uid="facturacion_pre_save")
def _captura_estado_previo(sender, instance, **kwargs):
    if not instance.pk:
        _estado_previo.pop(instance.pk, None)
        return
    try:
        from .models import Factura
        previo = Factura.objects.only("estado").get(pk=instance.pk)
        _estado_previo[instance.pk] = previo.estado
    except sender.DoesNotExist:
        pass


@receiver(post_save, sender="facturacion.Factura", dispatch_uid="facturacion_post_save")
def _hook_factura(sender, instance, created, update_fields=None, **kwargs):
    """Dispara asientos según transición de estado.

    - borrador → emitida: asiento auto_factura_emitida.
    - * → cancelada: asiento reverso auto_factura_cancelada (idempotente).
    """
    previo = _estado_previo.pop(instance.pk, None)

    transicion_a_emitida = (
        instance.estado == "emitida" and previo not in ("emitida", "cobrada_parcial", "cobrada_total")
    )
    transicion_a_cancelada = (
        instance.estado == "cancelada" and previo != "cancelada"
    )

    if transicion_a_emitida:
        transaction.on_commit(lambda: _generar_asiento_emision(instance))
    elif transicion_a_cancelada:
        transaction.on_commit(lambda: _generar_asiento_cancelacion(instance))


def _generar_asiento_emision(factura):
    """Asiento auto_factura_emitida:
       D cxc por total
       H ingreso_ventas por base (subtotal - descuento global)
       H iva_trasladado por trasladados totales
       D <slot retención> por cada retención
    Partida doble cuadra porque total = base + trasladados - retenciones.
    """
    from apps.contaduria.models import CuentaContable
    from apps.contaduria.services import AsientoInvalido, crear_asiento, cuenta_por_slot

    if not CuentaContable.objects.exists():
        return  # Catálogo no seedeado todavía.

    totales = factura.calcular_totales()
    total = totales["total"]
    base = totales["base_impuestos"]
    trasladados = totales["trasladados"]

    if total <= 0:
        log.warning("Factura %s con total %s — skip asiento.", factura.codigo, total)
        return

    cxc = cuenta_por_slot("cxc")
    ingresos = cuenta_por_slot("ingreso_ventas")
    if cxc is None or ingresos is None:
        log.warning("Catálogo incompleto: no se generó asiento para factura %s", factura.codigo)
        return

    from .contable import mapa_iva_para_tasa

    partidas = [
        {"cuenta": cxc, "cargo": total, "orden": 0,
         "descripcion": f"CxC {factura.cliente.razon_social[:120]}"},
        {"cuenta": ingresos, "abono": base, "orden": 1,
         "descripcion": f"Ingreso {factura.codigo}"},
    ]

    if trasladados > 0:
        iva_t = cuenta_por_slot("iva_trasladado")
        if iva_t is None:
            log.warning("Falta cuenta iva_trasladado — skip factura %s.", factura.codigo)
            return
        partidas.append({
            "cuenta": iva_t, "abono": trasladados, "orden": 2,
            "descripcion": "IVA trasladado",
        })

    orden = len(partidas)
    for imp in totales["impuestos_detalle"]:
        if imp["tipo"] != "retencion":
            continue
        # cargo a la cuenta espejo de retención (pasivo deudor o ISR retenido).
        slot = mapa_iva_para_tasa_por_dict(imp)
        cuenta_ret = cuenta_por_slot(slot)
        if cuenta_ret is None:
            log.warning("Falta cuenta slot=%s — skip retención de %s.", slot, factura.codigo)
            continue
        partidas.append({
            "cuenta": cuenta_ret, "cargo": imp["monto"], "orden": orden,
            "descripcion": imp["nombre"],
        })
        orden += 1

    try:
        crear_asiento(
            descripcion=f"Factura {factura.codigo} · {factura.titulo[:100]}",
            fecha=factura.fecha_emision,
            origen="auto_factura_emitida",
            referencia_externa=_ref_emitida(factura.pk),
            creado_por=factura.emitida_por or factura.creado_por,
            partidas=partidas,
            idempotente=True,
        )
    except AsientoInvalido as e:
        log.warning("Asiento de factura %s inválido: %s", factura.codigo, e)


def mapa_iva_para_tasa_por_dict(imp_dict) -> str:
    """Variante para el dict de `impuestos_detalle`. nombre + tipo."""
    tipo = (imp_dict.get("tipo") or "").lower()
    nombre = (imp_dict.get("nombre") or "").lower()
    if tipo == "trasladado":
        return "iva_trasladado"
    if tipo == "retencion":
        if "isr" in nombre:
            return "isr_retenido"
        return "iva_retenido_pagar"
    return ""


def _generar_asiento_cancelacion(factura):
    """Asiento reverso: invierte cargos/abonos del original. Idempotente."""
    from apps.contaduria.models import Asiento
    from apps.contaduria.services import AsientoInvalido, crear_asiento

    original = Asiento.vigentes.filter(
        referencia_externa=_ref_emitida(factura.pk),
        origen="auto_factura_emitida",
    ).first()
    if not original:
        return  # nunca se emitió → no hay nada que revertir.

    try:
        crear_asiento(
            descripcion=f"Cancelación de factura {factura.codigo}",
            fecha=(factura.cancelada_en.date() if factura.cancelada_en else factura.fecha_emision),
            origen="auto_factura_cancelada",
            referencia_externa=_ref_cancelada(factura.pk),
            creado_por=factura.cancelada_por,
            partidas=[
                {"cuenta": p.cuenta, "cargo": p.abono, "abono": p.cargo, "orden": p.orden}
                for p in original.partidas.all()
            ],
            idempotente=True,
        )
    except AsientoInvalido as e:
        log.warning("No se pudo crear reverso de factura %s: %s", factura.codigo, e)
