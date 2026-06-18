from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

AMBITO_CONOCIMIENTO = (
    ("finanzas", "Económicos / Finanzas"),
    ("cobranza", "Cobranza"),
    ("ventas", "Ventas"),
    ("margenes", "Costos y márgenes"),
)

ORIGEN_CONOCIMIENTO = (
    ("manual", "Capturado a mano"),
    ("chalan_destilado", "Destilado por el Chalán"),
)


class ConocimientoNegocio(models.Model):
    """Observación durable del negocio que fundamenta las OPINIONES del Chalán.

    Distinto de `DictadoAprendizaje` (que es pista de INTERPRETACIÓN de jerga):
    esto es CONOCIMIENTO del negocio — "el cliente X paga ~20 días tarde", "el
    margen de bordado es bajo", "las ventas caen en julio". El Chalán lo destila
    de los datos reales (`destilar_negocio.py`); nace INACTIVO y el super_admin
    lo revisa/aprueba en La Gerencia antes de que alimente las opiniones
    (review-first, mismo patrón que los aprendizajes).

    Decaimiento temporal: `peso_efectivo` decae linealmente a lo largo del año;
    bajo 0.3 deja de inyectarse en el contexto del Chalán.
    """

    ambito = models.CharField(max_length=20, choices=AMBITO_CONOCIMIENTO, db_index=True)
    observacion = models.CharField(max_length=400)
    evidencia = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=False)
    peso = models.FloatField(default=1.0)
    origen = models.CharField(max_length=20, choices=ORIGEN_CONOCIMIENTO, default="chalan_destilado")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conocimientos_negocio",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    desactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conocimientos_negocio_desactivados",
    )
    desactivado_en = models.DateTimeField(null=True, blank=True)
    motivo_desactivacion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "el_dictado_conocimiento_negocio"
        indexes = [
            models.Index(fields=["activo", "ambito"]),
            models.Index(fields=["-creado_en"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"conocimiento#{self.pk} [{self.ambito}] '{self.observacion[:40]}'"

    def peso_efectivo(self) -> float:
        if not self.activo:
            return 0.0
        dias = (timezone.now() - self.creado_en) // timedelta(days=1)
        decay = max(0.1, 1.0 - (dias / 365) * 0.9)
        return self.peso * decay
