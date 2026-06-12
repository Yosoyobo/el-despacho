"""HorarioLaboral — horario esperado por día. Global (usuario NULL) + overrides."""

from __future__ import annotations

from django.conf import settings
from django.db import models

# Convención: 0=lunes … 6=domingo (igual que date.weekday()).
DIAS_SEMANA = (
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
)


class HorarioLaboral(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="horarios_laborales",
        help_text="Vacío = horario global default para todo el staff.",
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()
    tolerancia_min = models.PositiveIntegerField(default=15, help_text="Minutos antes de marcar retardo")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "checador_horario"
        ordering = ["usuario_id", "dia_semana"]
        constraints = [
            # Un override por (usuario, día). El global (usuario NULL) lo
            # mantiene único el seed/CRUD (Postgres trata NULLs como distintos,
            # así que esta constraint no aplica a las filas globales).
            models.UniqueConstraint(
                fields=["usuario", "dia_semana"], name="checador_horario_usuario_dia",
            ),
        ]

    def __str__(self) -> str:
        quien = f"usuario {self.usuario_id}" if self.usuario_id else "global"
        return f"Horario {quien} · {self.get_dia_semana_display()} {self.hora_entrada}-{self.hora_salida}"
