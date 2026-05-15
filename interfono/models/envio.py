from __future__ import annotations

from django.conf import settings
from django.db import models


class InterfonoEnvio(models.Model):
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_interfono",
    )
    audiencia = models.CharField(max_length=40)
    audiencia_label = models.CharField(max_length=120)
    titulo = models.CharField(max_length=80)
    cuerpo = models.CharField(max_length=300)
    url_destino = models.TextField(blank=True, default="")
    entregadas = models.IntegerField(default=0)
    fallidas = models.IntegerField(default=0)
    suscripciones_invalidadas = models.IntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "interfono_envio"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"envio#{self.pk} {self.audiencia} '{self.titulo[:30]}'"
