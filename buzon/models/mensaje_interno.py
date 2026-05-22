"""El Buzón interno — mensajes de empleados al admin del despacho.

Tipos: sugerencia / problema / otro. El admin maneja estado y puede dejar
nota_interna (privada) y respuesta_publica (visible al autor).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPO_CHOICES = (
    ("sugerencia", "Sugerencia"),
    ("problema", "Problema / bug"),
    ("otro", "Otro"),
)
ESTADO_CHOICES = (
    ("nuevo", "Nuevo"),
    ("leido", "Leído"),
    ("respondido", "Respondido"),
    ("archivado", "Archivado"),
)


class MensajeBuzon(models.Model):
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mensajes_buzon"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="nuevo", db_index=True)
    prioridad = models.PositiveSmallIntegerField(
        default=5,
        db_index=True,
        help_text="Slider 0-10. 10 = más urgente.",
    )

    nota_interna = models.TextField(blank=True, default="")
    respuesta_publica = models.TextField(blank=True, default="")
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="buzon_respondidos",
    )
    respondido_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buzon_mensaje"
        ordering = ["-prioridad", "-creado_en"]
        verbose_name = "mensaje del Buzón"
        verbose_name_plural = "mensajes del Buzón"

    def __str__(self) -> str:
        return f"#{self.pk} {self.tipo} — {self.asunto[:40]}"
