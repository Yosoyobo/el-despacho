from django.conf import settings
from django.db import models


class Comentario(models.Model):
    """Comentario polimórfico: apunta a Tarea O Proyecto, nunca a ambos.

    CHECK constraint asegura exclusividad. El campo `es_interno` oculta el
    comentario a `disenador` que no es autor (visibilidad cliente más adelante
    en S5 podría reusar esta misma flag).
    """
    tarea = models.ForeignKey(
        "pizarron.Tarea", null=True, blank=True,
        on_delete=models.CASCADE, related_name="comentarios",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", null=True, blank=True,
        on_delete=models.CASCADE, related_name="comentarios",
    )
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comentarios")
    cuerpo = models.TextField()
    es_interno = models.BooleanField(default=False, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pizarron_comentario"
        ordering = ["-creado_en"]
        constraints = [
            models.CheckConstraint(
                # Exactamente uno de los dos debe ser NOT NULL.
                condition=(
                    models.Q(tarea__isnull=False, proyecto__isnull=True)
                    | models.Q(tarea__isnull=True, proyecto__isnull=False)
                ),
                name="pizarron_comentario_uno_de_dos",
            ),
        ]

    def __str__(self):
        destino = f"tarea#{self.tarea_id}" if self.tarea_id else f"proyecto#{self.proyecto_id}"
        return f"{self.autor_id}@{destino}"

    @property
    def destino_proyecto(self):
        return self.proyecto or (self.tarea.proyecto if self.tarea_id else None)
