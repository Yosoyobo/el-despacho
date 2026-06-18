"""Vista compartida de `el_dictado_conocimiento_negocio` para Gerencia.

El esquema lo mantiene `apps.el_dictado.models.ConocimientoNegocio` (Taller).
Este modelo es `managed = False` y apunta al MISMO `db_table`, para que La
Gerencia (que no instala `apps.el_dictado`) pueda revisar/activar el
conocimiento de negocio del Chalán sin duplicar el schema. Mismo patrón que
`chalanes.models.Aprendizaje`.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ConocimientoNegocio(models.Model):
    """Observación durable del negocio (review-first) — shadow de Gerencia."""

    ambito = models.CharField(max_length=20, db_index=True)
    observacion = models.CharField(max_length=400)
    evidencia = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=False)
    peso = models.FloatField(default=1.0)
    origen = models.CharField(max_length=20, default="chalan_destilado")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", db_column="autor_id",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    desactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", db_column="desactivado_por_id",
    )
    desactivado_en = models.DateTimeField(null=True, blank=True)
    motivo_desactivacion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        app_label = "chalanes"
        db_table = "el_dictado_conocimiento_negocio"
        managed = False
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"conocimiento#{self.pk} [{self.ambito}] '{self.observacion[:40]}'"

    def peso_efectivo(self) -> float:
        if not self.activo:
            return 0.0
        dias = (timezone.now() - self.creado_en) // timedelta(days=1)
        decay = max(0.1, 1.0 - (dias / 365) * 0.9)
        return self.peso * decay
