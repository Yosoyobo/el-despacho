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
    from . import gastos
    from .models import Proyecto

    proyecto = Proyecto.objects.filter(pk=proyecto_id).first()
    if proyecto is None:
        return

    # Cada gasto (producto + impresión + operativo) se liga por separado a su
    # propio egreso (decisión Oscar 2026-06-12). Idempotente: solo los que no
    # tienen egreso vigente. Silent-skip si el centro de costo está ausente.
    generados = gastos.registrar_pendientes(proyecto)
    if not generados:
        return
    with contextlib.suppress(Exception):
        from . import servicios_actividad
        servicios_actividad.registrar(
            proyecto=proyecto, tipo="egreso_generado",
            descripcion=f"{len(generados)} egreso(s) generado(s) al entrar a producción",
            actor=None, url=f"/proyectos/{proyecto.pk}/",
        )
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
