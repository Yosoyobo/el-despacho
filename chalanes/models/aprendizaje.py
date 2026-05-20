"""Vista compartida de `el_dictado_aprendizaje` para Gerencia y Taller.

El esquema lo mantiene `apps.el_dictado.models.DictadoAprendizaje` (Taller).
Este modelo es `managed = False` y apunta al MISMO `db_table`, para que
La Gerencia (que no instala `apps.el_dictado`) pueda gestionar los
aprendizajes sin duplicar el schema.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Aprendizaje(models.Model):
    """Frase/patrón que el equipo le enseñó al Chalán Claudio.

    Decaimiento temporal: el peso decae linealmente a lo largo del año;
    bajo 0.3 el aprendizaje deja de inyectarse en el prompt del Dictado.
    """

    # Referencia plana al dictado de origen — sin FK porque `el_dictado`
    # vive sólo en Taller. La Gerencia no necesita navegar el grafo.
    dictado_origen_id = models.BigIntegerField(null=True, blank=True, db_column="dictado_origen_id")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="+", db_column="autor_id",
    )
    frase_o_patron = models.CharField(max_length=300)
    interpretacion_correcta = models.TextField()
    activo = models.BooleanField(default=True)
    peso = models.FloatField(default=1.0)
    creado_en = models.DateTimeField(auto_now_add=True)
    desactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", db_column="desactivado_por_id",
    )
    desactivado_en = models.DateTimeField(null=True, blank=True)
    motivo_desactivacion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        app_label = "chalanes"
        db_table = "el_dictado_aprendizaje"
        managed = False
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"aprendizaje#{self.pk} '{self.frase_o_patron[:40]}'"

    def peso_efectivo(self) -> float:
        if not self.activo:
            return 0.0
        dias = (timezone.now() - self.creado_en) // timedelta(days=1)
        decay = max(0.1, 1.0 - (dias / 365) * 0.9)
        return self.peso * decay
