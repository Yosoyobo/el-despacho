from __future__ import annotations

from django.conf import settings
from django.db import models


class RecadoVersion(models.Model):
    recado = models.ForeignKey(
        "recados.Recado", on_delete=models.CASCADE, related_name="versiones"
    )
    version = models.IntegerField()
    cuerpo = models.TextField()
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    editado_en = models.DateTimeField()

    class Meta:
        db_table = "recado_version"
        unique_together = [("recado", "version")]
        ordering = ["recado", "version"]

    def __str__(self) -> str:
        return f"recado#{self.recado_id} v{self.version}"
