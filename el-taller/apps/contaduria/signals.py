"""Signals que generan asientos contables automáticos al registrar
movimientos en Tesorería.

Patrón:
- `post_save` Ingreso (created=True, no anulado) → asiento auto_ingreso.
- `post_save` Egreso (created=True, no anulado) → asiento auto_egreso.
- `post_save` con `anulado=True` que antes no lo estaba → asiento reverso
  (manejado via `update_fields` y comparación de pre_save).

Idempotencia: `crear_asiento(referencia_externa=...)` evita duplicados
si el signal vuelve a dispararse por cualquier razón.

Si las cuentas slot necesarias no existen (catálogo incompleto), el
signal hace silent skip y emite warning. Nunca tumba la transacción de
Tesorería — la contabilidad es secundaria a la operación.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

log = logging.getLogger("despacho.contaduria")


def _en_test_sin_settings() -> bool:
    """Permite skip durante migraciones iniciales si las cuentas no están
    seedeadas todavía. La migración 0002_seed_cuentas las crea."""
    from .models import CuentaContable
    return not CuentaContable.objects.exists()


def _cuenta_efectivo_o_banco(metodo: str):
    """Para un Ingreso: efectivo → caja; otros métodos → bancos."""
    from .services import cuenta_por_slot
    if metodo == "efectivo":
        return cuenta_por_slot("caja")
    return cuenta_por_slot("banco")


def _cuenta_salida_egreso(metodo: str, estado_pago: str):
    """Para un Egreso: la contracuenta de salida según método y estado.

    - tarjeta_personal + por_reembolsar → cuenta 'reembolsos' (pasivo)
    - estado_pago=pendiente → cuenta 'cxp' (Proveedores)
    - efectivo → 'caja'
    - otros (transferencia/tarjeta_empresa/cheque) → 'banco'
    """
    from .services import cuenta_por_slot
    if estado_pago == "por_reembolsar":
        return cuenta_por_slot("reembolsos")
    if estado_pago == "pendiente":
        return cuenta_por_slot("cxp")
    if metodo == "efectivo":
        return cuenta_por_slot("caja")
    return cuenta_por_slot("banco")


def _ref(modelo: str, pk: int) -> str:
    return f"{modelo}:{pk}"


# Cache de pre_save para detectar transición a anulado
_estado_previo: dict[str, bool] = {}


@receiver(post_save, sender="tesoreria.Ingreso", dispatch_uid="contaduria_ingreso")
def _hook_ingreso(sender, instance, created, update_fields=None, **kwargs):
    from .services import AsientoInvalido, crear_asiento, cuenta_por_slot

    if instance.anulado:
        # ¿Es transición a anulado? Buscar asiento original y revertir.
        ref_original = _ref("tesoreria.ingreso", instance.pk)
        from .models import Asiento
        original = Asiento.vigentes.filter(referencia_externa=ref_original, origen="auto_ingreso").first()
        if not original:
            return
        # Crear asiento reverso si no existe ya.
        ref_reverso = _ref("tesoreria.ingreso.anulacion", instance.pk)
        try:
            crear_asiento(
                descripcion=f"Anulación de ingreso {instance.codigo}",
                fecha=instance.anulado_en.date() if instance.anulado_en else instance.fecha,
                origen="auto_anulacion_ingreso",
                referencia_externa=ref_reverso,
                partidas=[
                    {"cuenta": p.cuenta, "cargo": p.abono, "abono": p.cargo, "orden": p.orden}
                    for p in original.partidas.all()
                ],
                idempotente=True,
            )
        except AsientoInvalido as e:
            log.warning("No se pudo crear reverso de ingreso %s: %s", instance.codigo, e)
        return

    if not created:
        return  # Edición sin cambios contables relevantes en V1.

    if _en_test_sin_settings():
        return

    contra = _cuenta_efectivo_o_banco(instance.metodo)
    # S2b.facturacion-v1: si el Ingreso es un cobro de Factura, la
    # contracuenta es CxC (cancelamos la cuenta por cobrar). El ingreso
    # ya se reconoció contablemente al EMITIR la factura, no aquí.
    if getattr(instance, "factura_id", None):
        contracuenta = cuenta_por_slot("cxc")
        descripcion_contra = f"Cobro CxC {instance.descripcion[:100]}"
    else:
        contracuenta = cuenta_por_slot("ingreso_ventas")
        descripcion_contra = instance.descripcion[:120]
    if contra is None or contracuenta is None:
        log.warning("Catálogo incompleto: no se generó asiento para ingreso %s", instance.codigo)
        return

    def _crear():
        try:
            crear_asiento(
                descripcion=f"Ingreso {instance.codigo} · {instance.descripcion[:120]}",
                fecha=instance.fecha,
                origen="auto_ingreso",
                referencia_externa=_ref("tesoreria.ingreso", instance.pk),
                creado_por=instance.creado_por,
                partidas=[
                    {"cuenta": contra, "cargo": instance.monto, "orden": 0,
                     "descripcion": f"{instance.metodo}"},
                    {"cuenta": contracuenta, "abono": instance.monto, "orden": 1,
                     "descripcion": descripcion_contra},
                ],
                idempotente=True,
            )
        except AsientoInvalido as e:
            log.warning("Asiento de ingreso %s inválido: %s", instance.codigo, e)

    transaction.on_commit(_crear)


@receiver(post_save, sender="tesoreria.Egreso", dispatch_uid="contaduria_egreso")
def _hook_egreso(sender, instance, created, update_fields=None, **kwargs):
    from .services import AsientoInvalido, crear_asiento, cuenta_por_slot

    if instance.anulado:
        ref_original = _ref("tesoreria.egreso", instance.pk)
        from .models import Asiento
        original = Asiento.vigentes.filter(referencia_externa=ref_original, origen="auto_egreso").first()
        if not original:
            return
        ref_reverso = _ref("tesoreria.egreso.anulacion", instance.pk)
        try:
            crear_asiento(
                descripcion=f"Anulación de egreso {instance.codigo}",
                fecha=instance.anulado_en.date() if instance.anulado_en else instance.fecha,
                origen="auto_anulacion_egreso",
                referencia_externa=ref_reverso,
                partidas=[
                    {"cuenta": p.cuenta, "cargo": p.abono, "abono": p.cargo, "orden": p.orden}
                    for p in original.partidas.all()
                ],
                idempotente=True,
            )
        except AsientoInvalido as e:
            log.warning("No se pudo crear reverso de egreso %s: %s", instance.codigo, e)
        return

    if not created:
        return

    if _en_test_sin_settings():
        return

    gasto = cuenta_por_slot("egreso_operativo")
    salida = _cuenta_salida_egreso(instance.metodo, instance.estado_pago)
    if gasto is None or salida is None:
        log.warning("Catálogo incompleto: no se generó asiento para egreso %s", instance.codigo)
        return

    def _crear():
        try:
            crear_asiento(
                descripcion=f"Egreso {instance.codigo} · {instance.descripcion[:120]}",
                fecha=instance.fecha,
                origen="auto_egreso",
                referencia_externa=_ref("tesoreria.egreso", instance.pk),
                creado_por=instance.creado_por,
                partidas=[
                    {"cuenta": gasto, "cargo": instance.monto, "orden": 0,
                     "descripcion": instance.descripcion[:120]},
                    {"cuenta": salida, "abono": instance.monto, "orden": 1,
                     "descripcion": f"{instance.metodo} · {instance.estado_pago}"},
                ],
                idempotente=True,
            )
        except AsientoInvalido as e:
            log.warning("Asiento de egreso %s inválido: %s", instance.codigo, e)

    transaction.on_commit(_crear)
