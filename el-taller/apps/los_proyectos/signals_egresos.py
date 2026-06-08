"""Genera Egresos en Tesorería cuando un proyecto pasa a producción.

Decisión (Oscar, 2026-06-07): al cambiar el estado de un proyecto a
`en_proceso_produccion`, cada línea de producto incluida con costo > 0 genera
UN Egreso (granularidad por línea). Idempotente: una línea que ya tiene
`egreso` NO vuelve a generar. Así los gastos del proyecto se reflejan en
Tesorería (y de ahí el Chalán los puede reportar) y disparan el asiento
`auto_egreso` de Contaduría → CxP por proveedor.

Defensa en profundidad: si el catálogo de centros de costo está incompleto,
se omite la generación SIN tumbar el guardado del proyecto (mismo criterio que
los signals de Contaduría). Sólo dispara en la TRANSICIÓN a producción, no en
cada save posterior estando ya en producción.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

ESTADO_PRODUCCION = "en_proceso_produccion"
CENTRO_SLUG = "insumos-de-proyecto"
CERO = Decimal("0.00")


@receiver(pre_save, sender="proyectos.Proyecto", dispatch_uid="proyectos_egresos_presave")
def _capturar_estado_previo(sender, instance, **kwargs):  # noqa: ARG001
    if not instance.pk:
        instance._estado_previo = None
        return
    try:
        instance._estado_previo = sender.objects.only("estado").get(pk=instance.pk).estado
    except sender.DoesNotExist:
        instance._estado_previo = None


@receiver(post_save, sender="proyectos.Proyecto", dispatch_uid="proyectos_egresos_postsave")
def _generar_egresos_al_entrar_produccion(sender, instance, created, **kwargs):  # noqa: ARG001
    if instance.estado != ESTADO_PRODUCCION:
        return
    previo = getattr(instance, "_estado_previo", None)
    if previo == ESTADO_PRODUCCION:
        return  # ya estaba en producción — no es transición
    pk = instance.pk
    transaction.on_commit(lambda: _crear_egresos_de_proyecto(pk))


def _crear_egresos_de_proyecto(proyecto_id: int) -> None:
    from apps.tesoreria.models import CentroDeCosto, Egreso

    from .models import Proyecto

    proyecto = Proyecto.objects.filter(pk=proyecto_id).first()
    if proyecto is None:
        return
    centro = CentroDeCosto.objects.filter(slug=CENTRO_SLUG).first()
    if centro is None:
        logger.warning(
            "proyecto=%s: centro '%s' ausente — no se generan egresos.",
            proyecto_id, CENTRO_SLUG,
        )
        return

    generados = []
    with transaction.atomic():
        lineas = (
            proyecto.productos
            .select_related("proveedor", "servicio", "variacion")
            .prefetch_related("procesos")
        )
        for pp in lineas:
            if not pp.incluir_en_calculo or pp.egreso_id:
                continue
            monto = Decimal(str(pp.costo_total_con_procesos)).quantize(Decimal("0.01"))
            if monto <= 0:
                continue
            egreso = Egreso.objects.create(
                monto=monto,
                fecha=date.today(),
                descripcion=f"Proyecto {proyecto.codigo} · {pp.etiqueta}"[:300],
                proveedor=pp.proveedor,
                proveedor_nombre=(
                    pp.proveedor.razon_social if pp.proveedor_id else "Gasto de proyecto"
                )[:200],
                centro_de_costo=centro,
                proyecto=proyecto,
                estado_pago="pendiente",
                metodo="transferencia",
                origen="proyecto",
            )
            pp.egreso = egreso
            pp.save(update_fields=["egreso"])
            generados.append(egreso)

    if not generados:
        return
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="proyecto.egresos_generados",
            actor_id=None, actor_email=None,
            payload={
                "proyecto_id": proyecto.pk,
                "codigo": proyecto.codigo,
                "egresos": len(generados),
                "total": float(sum((e.monto for e in generados), CERO)),
            },
        ))
