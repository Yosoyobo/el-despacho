"""SolicitudCorreccion — el usuario pide ajustar una marca; el admin resuelve."""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPO_CORRECCION = (
    ("entrada", "Hora de entrada"),
    ("salida", "Hora de salida"),
    ("visita", "Hora de visita"),
    ("sesion", "Sesión de proyecto"),
)

ESTADO_CORRECCION = (
    ("pendiente", "Pendiente"),
    ("aprobada", "Aprobada"),
    ("rechazada", "Rechazada"),
)


class SolicitudCorreccion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="correcciones_checador",
    )
    jornada = models.ForeignKey(
        "checador.Jornada", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="correcciones",
    )
    sesion = models.ForeignKey(
        "checador.SesionProyecto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="correcciones",
    )
    visita = models.ForeignKey(
        "checador.Visita", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="correcciones",
    )

    tipo = models.CharField(max_length=10, choices=TIPO_CORRECCION)
    valor_propuesto = models.DateTimeField(help_text="Nuevo valor solicitado")
    motivo = models.TextField()

    estado = models.CharField(max_length=10, choices=ESTADO_CORRECCION, default="pendiente")
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="correcciones_resueltas",
    )
    resuelto_en = models.DateTimeField(null=True, blank=True)
    comentario_admin = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checador_correccion"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["estado", "creado_en"])]

    def __str__(self) -> str:
        return f"Corrección {self.tipo} · {self.usuario_id} ({self.estado})"
