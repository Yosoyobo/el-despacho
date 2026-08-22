"""Avisa al cliente cuando su proyecto cambia de estado — si hay una regla.

El disparo va por `transaction.on_commit`: sin eso, un rollback posterior
dejaría al cliente con un correo de algo que nunca pasó. Y el aviso es
best-effort de punta a punta — `lib.reglas_correo.disparar` no lanza, así que
guardar el proyecto no puede fallar por culpa del correo.

Se separa de `signals_egresos` a propósito: son dos reglas de negocio distintas
sobre la misma transición, y mezclarlas haría que un fallo de una arrastre a la
otra.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender="proyectos.Proyecto", dispatch_uid="proyectos_correo_presave")
def _capturar_estado_previo(sender, instance, **kwargs):  # noqa: ARG001
    """Guarda el estado que tenía antes, para reconocer la TRANSICIÓN.

    Sin esto, cada guardado de un proyecto ya entregado volvería a mandar el
    aviso. (El candado de `CorreoEnviadoRegla` lo atraparía igual, pero más
    vale no depender sólo de la última línea de defensa.)
    """
    if not instance.pk:
        instance._estado_previo_correo = None
        return
    try:
        instance._estado_previo_correo = (
            sender.objects.only("estado").get(pk=instance.pk).estado
        )
    except sender.DoesNotExist:
        instance._estado_previo_correo = None


@receiver(post_save, sender="proyectos.Proyecto", dispatch_uid="proyectos_correo_postsave")
def _avisar_cambio_de_estado(sender, instance, created, **kwargs):  # noqa: ARG001
    previo = getattr(instance, "_estado_previo_correo", None)
    if created or previo is None or previo == instance.estado:
        return
    estado_nuevo = instance.estado

    def _disparar():
        from lib import reglas_correo
        reglas_correo.proyecto_cambio_estado(instance, estado_nuevo)

    transaction.on_commit(_disparar)
