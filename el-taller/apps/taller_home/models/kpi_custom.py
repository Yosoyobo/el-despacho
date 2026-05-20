"""KPICustom — KPIs generados por el Chalán a partir de NL (S2b.5).

El Chalán Claudio traduce una pregunta en lenguaje natural a un DSL JSON
acotado. El DSL se ejecuta vía query builder vetado (NUNCA SQL/ORM libre).

Alcance:
- `personal`: lo ve sólo el autor. No requiere aprobación.
- `equipo`: visible a todos los roles permitidos. Requiere aprobación
  super_admin (cualquier rol puede proponer, super_admin aprueba).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

ALCANCES = (
    ("personal", "Personal — sólo yo lo veo"),
    ("equipo", "Equipo — visible a todo el despacho"),
)

ESTADOS = (
    ("activo", "Activo"),
    ("pendiente_aprobacion", "Pendiente de aprobación"),
    ("rechazado", "Rechazado"),
    ("archivado", "Archivado por el autor"),
)


class KPICustom(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    titulo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, default="")
    definicion_json = models.JSONField()
    alcance = models.CharField(max_length=20, choices=ALCANCES, default="personal")
    categoria = models.CharField(max_length=30, default="custom")
    estado = models.CharField(max_length=30, choices=ESTADOS, default="activo", db_index=True)

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="kpis_custom_creados",
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kpis_custom_aprobados",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.CharField(max_length=300, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "taller_home_kpi_custom"
        indexes = [
            models.Index(fields=["alcance", "estado"]),
            models.Index(fields=["autor", "estado"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"kpi_custom#{self.pk} {self.slug} ({self.alcance})"

    def requiere_aprobacion(self) -> bool:
        return self.alcance == "equipo" and self.estado == "pendiente_aprobacion"
