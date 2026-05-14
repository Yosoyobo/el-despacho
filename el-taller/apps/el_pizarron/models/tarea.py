from django.conf import settings
from django.db import models


ESTADOS_TAREA = (
    ("pendiente", "Pendiente"),
    ("en_curso", "En curso"),
    ("bloqueada", "Bloqueada"),
    ("completada", "Completada"),
)

PRIORIDADES = (
    ("baja", "Baja"),
    ("media", "Media"),
    ("alta", "Alta"),
)


class Tarea(models.Model):
    proyecto = models.ForeignKey("proyectos.Proyecto", on_delete=models.CASCADE, related_name="tareas")
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS_TAREA, default="pendiente", db_index=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default="media")
    asignada_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tareas_asignadas",
    )
    fecha_compromiso = models.DateField(null=True, blank=True)
    completada_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tareas_creadas",
    )

    class Meta:
        db_table = "pizarron_tarea"
        verbose_name = "tarea"
        verbose_name_plural = "tareas"
        ordering = ["estado", "-creado_en"]

    def __str__(self):
        return self.titulo
