from django.conf import settings
from django.db import models


ROLES_PROYECTO = (
    ("lider", "Líder"),
    ("disenador", "Diseñador"),
    ("produccion", "Producción"),
    ("revisor", "Revisor"),
)


class ProyectoAsignacion(models.Model):
    proyecto = models.ForeignKey("proyectos.Proyecto", on_delete=models.CASCADE, related_name="asignaciones")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="asignaciones_proyecto")
    rol_en_proyecto = models.CharField(max_length=20, choices=ROLES_PROYECTO, default="disenador")
    asignado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_asignacion"
        verbose_name = "asignación"
        verbose_name_plural = "asignaciones"
        constraints = [
            models.UniqueConstraint(fields=["proyecto", "usuario"], name="proyectos_asignacion_unica"),
        ]

    def __str__(self):
        return f"{self.usuario.email} → {self.proyecto.codigo} ({self.rol_en_proyecto})"
