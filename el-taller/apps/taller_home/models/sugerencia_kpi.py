from __future__ import annotations

from django.conf import settings
from django.db import models


class SugerenciaKPI(models.Model):
    """Sugerencias del Chalán Claudio (Capa 2) de KPIs nuevos para el usuario.

    Se generan vía reglas heurísticas (siempre activas) y, en S2b.2+, también
    vía llamadas al LLM del Chalán Claudio. El usuario las ve como banner en
    Sala de Juntas y puede aceptar (→ crea `PreferenciaKPI(visible=True)`) o
    descartar (→ `estado='descartada'`, no se vuelve a sugerir el mismo slug).
    """

    ESTADOS = (
        ("pendiente", "Pendiente"),
        ("aceptada", "Aceptada"),
        ("descartada", "Descartada"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sugerencias_kpi",
    )
    kpi_slug = models.CharField(max_length=80)
    motivo = models.TextField(blank=True, default="")
    fuente = models.CharField(max_length=30, default="heuristica")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    sugerido_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "taller_home_sugerencia_kpi"
        unique_together = [("usuario", "kpi_slug")]
        ordering = ["-sugerido_en"]

    def __str__(self) -> str:
        return f"sugerencia u={self.usuario_id} kpi={self.kpi_slug} {self.estado}"
