"""Hilo de comentarios de un mensaje del Buzón (S-LC-Buzon-V2 / C5d).

Conversación ida y vuelta autor↔admin dentro de un ticket. Quién puede
responder se gobierna por permiso (admins siempre) + el toggle global
`ConfiguracionBuzon.empleado_puede_responder` (default: el empleado NO responde).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ConfiguracionBuzon(models.Model):
    """Singleton (pk=1) con ajustes globales del Buzón."""

    empleado_puede_responder = models.BooleanField(
        default=False,
        help_text="Si está activo, el autor del mensaje puede responder en su propio ticket.",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buzon_configuracion"
        verbose_name = "configuración del Buzón"
        verbose_name_plural = "configuración del Buzón"

    @classmethod
    def obtener(cls) -> ConfiguracionBuzon:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configuración del Buzón"


class MensajeBuzonComentario(models.Model):
    mensaje = models.ForeignKey(
        "buzon.MensajeBuzon", on_delete=models.CASCADE, related_name="comentarios"
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="comentarios_buzon",
    )
    cuerpo = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "buzon_comentario"
        ordering = ["creado_en"]
        indexes = [models.Index(fields=["mensaje", "creado_en"])]

    def __str__(self):
        return f"comentario #{self.pk} en buzón #{self.mensaje_id}"
