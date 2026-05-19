from __future__ import annotations

from django.conf import settings
from django.db import models


class RecadoDestinatario(models.Model):
    recado = models.ForeignKey(
        "recados.Recado", on_delete=models.CASCADE, related_name="destinatarios"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recados_recibidos",
    )
    leido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recado_destinatario"
        unique_together = [("recado", "usuario")]
        indexes = [
            models.Index(fields=["usuario", "-recado"]),
            models.Index(fields=["usuario", "leido_en"]),
        ]

    def __str__(self) -> str:
        return f"dest u={self.usuario_id} r={self.recado_id}"
