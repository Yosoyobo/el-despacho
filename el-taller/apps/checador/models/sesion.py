"""SesionProyecto — tiempo dedicado a un proyecto (timer o captura manual)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

ORIGEN_SESION = (
    ("timer", "Cronómetro"),
    ("manual", "Captura manual"),
)

ESTADO_SESION = (
    ("activa", "Activa"),
    ("cerrada", "Cerrada"),
)


class SesionProyecto(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sesiones_proyecto",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.CASCADE, related_name="sesiones_checador",
    )
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    duracion_min = models.PositiveIntegerField(null=True, blank=True, help_text="Derivada al cerrar")
    origen = models.CharField(max_length=8, choices=ORIGEN_SESION, default="timer")
    nota = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=8, choices=ESTADO_SESION, default="activa")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checador_sesion_proyecto"
        ordering = ["-inicio"]
        indexes = [
            models.Index(fields=["usuario", "estado"]),
            models.Index(fields=["proyecto", "inicio"]),
        ]

    def __str__(self) -> str:
        return f"Sesión {self.usuario_id} · {self.proyecto_id} ({self.estado})"

    def cerrar(self, *, fin) -> None:
        """Cierra la sesión y calcula la duración en minutos (mín. 0)."""
        self.fin = fin
        delta = (fin - self.inicio).total_seconds() / 60
        self.duracion_min = max(0, int(delta))
        self.estado = "cerrada"
