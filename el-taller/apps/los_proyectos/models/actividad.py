"""Feed de actividad por proyecto (S-Recados-V2 / C5b).

Cada evento relevante de un proyecto (cambio de estado, nueva tarea, comentario,
fecha por vencer, egreso generado) deja una fila aquí. El tab "Actividad" de
Recados muestra, a los líderes, el feed de sus proyectos — con deep-link.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPOS_ACTIVIDAD = (
    ("estado_cambiado", "Cambio de estado"),
    ("tarea_creada", "Nueva tarea"),
    ("comentario", "Comentario"),
    ("fecha_por_vencer", "Fecha por vencer"),
    ("egreso_generado", "Egreso generado"),
)


class ActividadProyecto(models.Model):
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.CASCADE, related_name="actividades"
    )
    tipo = models.CharField(max_length=24, choices=TIPOS_ACTIVIDAD, db_index=True)
    descripcion = models.CharField(max_length=255)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="actividades_proyecto",
    )
    url = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "proyectos_actividad"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["proyecto", "-creado_en"])]

    def __str__(self):
        return f"{self.proyecto_id} · {self.tipo}"
