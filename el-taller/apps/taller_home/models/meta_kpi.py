"""S-LC-Feedback-V5 c8 — Metas configurables por KPI.

Cada KPI del catálogo (slug, ej. `ingresos-mes`) puede tener una meta
asociada. El `_kpi_card_hero.html` muestra barra de progreso si la meta
existe, y opcionalmente gauge/bullet en ApexCharts cuando el visual_tipo
lo amerite.

Solo super_admin las edita desde `/ajustes/metas-kpi/`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

PERIODOS = (
    ("mes", "Mensual"),
    ("trimestre", "Trimestral"),
    ("ano", "Anual"),
)


class MetaKPI(models.Model):
    kpi_slug = models.CharField(max_length=80, unique=True, db_index=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    periodo = models.CharField(max_length=20, choices=PERIODOS, default="mes")
    activa = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="metas_kpi_modificadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "taller_home_meta_kpi"
        ordering = ["kpi_slug"]

    def __str__(self) -> str:
        return f"{self.kpi_slug} = {self.valor} ({self.periodo})"
