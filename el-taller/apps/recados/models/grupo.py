from __future__ import annotations

from django.db import models

TIPOS_GRUPO = [
    ("estatico", "Estático"),
    ("rol", "Por rol"),
    ("dinamico", "Dinámico"),
]


class RecadoGrupo(models.Model):
    """Grupos predefinidos para envío masivo (DOC_03 §3.5).

    Los grupos `tipo='rol'` expanden a usuarios activos con esos roles.
    El grupo dinámico `equipo-de-#proyecto` NO se persiste; se resuelve
    al crear el recado leyendo el slug del proyecto.
    """

    slug = models.CharField(max_length=50, primary_key=True)
    nombre_legible = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True, default="")
    tipo = models.CharField(max_length=20, choices=TIPOS_GRUPO)
    roles = models.JSONField(default=list, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recado_grupo"
        ordering = ["slug"]

    def __str__(self) -> str:
        return f"{self.slug} ({self.tipo})"
