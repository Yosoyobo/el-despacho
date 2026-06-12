"""RecordatorioEntrada — dedup de los avisos "checa tu entrada".

Una fila por (usuario, día): se crea cuando se le manda el recordatorio de
que aún no checa su entrada después de su hora. El cron lo consulta para no
repetir el aviso el mismo día.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class RecordatorioEntrada(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="recordatorios_entrada_checador",
    )
    fecha = models.DateField(db_index=True)
    enviado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checador_recordatorio_entrada"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "fecha"], name="checador_recordatorio_entrada_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"Recordatorio entrada {self.usuario_id} · {self.fecha}"
