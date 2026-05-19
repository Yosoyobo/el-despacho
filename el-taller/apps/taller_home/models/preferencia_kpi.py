from __future__ import annotations

from django.conf import settings
from django.db import models


class PreferenciaKPI(models.Model):
    """Preferencia por-usuario para mostrar/ocultar un KPI en la Sala de Juntas.

    Default opt-in: si NO existe fila para (usuario, kpi_slug), el KPI se
    considera visible (siempre y cuando el rol del usuario lo permita).
    Sólo se persiste cuando el usuario explícitamente desactiva un KPI
    (o lo reactiva después).

    `origen` discrimina entre:
    - `manual`: KPI del catálogo declarativo en `kpis.py`
    - `sugerido_chalan`: futuro (S2b.2+) — KPI propuesto por el Chalán
    - `custom_chalan`: futuro (S2b.5) — KPI creado vía DSL

    `orden` permite reordenar las cards (botones up/down en la UI). Default
    `None` = orden natural del catálogo.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferencias_kpi",
    )
    kpi_slug = models.CharField(max_length=80)
    visible = models.BooleanField(default=True)
    orden = models.IntegerField(null=True, blank=True)
    origen = models.CharField(max_length=20, default="manual")
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "taller_home_preferencia_kpi"
        unique_together = [("usuario", "kpi_slug")]
        indexes = [
            models.Index(fields=["usuario", "visible"]),
        ]

    def __str__(self) -> str:
        return f"pref kpi u={self.usuario_id} {self.kpi_slug} visible={self.visible}"
