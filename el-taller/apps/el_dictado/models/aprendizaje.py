from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DictadoAprendizaje(models.Model):
    """Frase/patrón que el equipo le enseñó al Chalán Claudio.

    El sistema captura cuando el usuario clarifica una ambigüedad o desmarca
    una acción. El super_admin gestiona (UI llega en sub-sprint S2b.2.1).

    Decaimiento temporal: peso_efectivo decae linealmente a lo largo del
    año; bajo 0.3 el aprendizaje no se inyecta en el prompt.
    """

    dictado_origen = models.ForeignKey(
        "el_dictado.Dictado", on_delete=models.SET_NULL, null=True,
        related_name="aprendizajes_generados",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="aprendizajes_que_enseno",
    )
    frase_o_patron = models.CharField(max_length=300)
    interpretacion_correcta = models.TextField()
    activo = models.BooleanField(default=True)
    peso = models.FloatField(default=1.0)
    creado_en = models.DateTimeField(auto_now_add=True)
    desactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="aprendizajes_desactivados",
    )
    desactivado_en = models.DateTimeField(null=True, blank=True)
    motivo_desactivacion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "el_dictado_aprendizaje"
        indexes = [
            models.Index(fields=["activo", "-creado_en"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"aprendizaje#{self.pk} '{self.frase_o_patron[:40]}'"

    def peso_efectivo(self) -> float:
        if not self.activo:
            return 0.0
        dias = (timezone.now() - self.creado_en) // timedelta(days=1)
        decay = max(0.1, 1.0 - (dias / 365) * 0.9)
        return self.peso * decay
