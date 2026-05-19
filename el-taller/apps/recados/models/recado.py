from __future__ import annotations

from django.conf import settings
from django.db import models


class Recado(models.Model):
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recados_enviados",
    )
    cuerpo = models.TextField()
    cuerpo_normalizado = models.TextField(blank=True, default="")

    editado = models.BooleanField(default=False)
    editado_en = models.DateTimeField(null=True, blank=True)
    version_actual = models.IntegerField(default=1)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recado"
        indexes = [
            models.Index(fields=["-creado_en"]),
            models.Index(fields=["autor", "-creado_en"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"recado#{self.pk} autor={self.autor_id}"

    @property
    def cuerpo_para_push(self) -> str:
        """Primeros caracteres del cuerpo, sin los tokens `@/#/$` (DOC_03 §7.2)."""
        import re
        limpio = re.sub(r"(?<![A-Za-z0-9_])[@#$]([A-Za-z0-9_-]{1,80})", r"\1", self.cuerpo or "")
        return limpio.strip()
