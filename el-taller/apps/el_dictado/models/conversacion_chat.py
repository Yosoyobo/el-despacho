from __future__ import annotations

from django.conf import settings
from django.db import models

ROLES_MENSAJE = (
    ("user", "Usuario"),
    ("bot", "El Chalán"),
)

TIPOS_MENSAJE = (
    ("texto", "Texto"),
    ("herramienta", "Resultado de herramienta"),
    ("accion", "Propuesta de acción"),
)


class ConversacionChat(models.Model):
    """Una sesión de chat con El Chalán. Efímera en intención (sin re-alimentar
    historial largo al LLM) pero persistida para poder navegar conversaciones
    pasadas desde la lista lateral del chat."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversaciones_chat",
    )
    # Auto-derivado del primer mensaje del usuario (truncado ~60 chars).
    titulo = models.CharField(max_length=120, blank=True, default="")
    archivada = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "el_dictado_conversacion_chat"
        indexes = [
            models.Index(fields=["usuario", "-actualizado_en"]),
        ]
        ordering = ["-actualizado_en"]

    def __str__(self) -> str:
        return f"chat#{self.pk} '{self.titulo[:40]}'"


class MensajeChat(models.Model):
    """Un turno renderizable de la conversación. Los pasos intermedios de
    herramientas NO se guardan como mensajes (solo el par usuario↔respuesta y,
    opcionalmente, una tarjeta informativa colapsada)."""

    conversacion = models.ForeignKey(
        ConversacionChat, on_delete=models.CASCADE, related_name="mensajes"
    )
    orden = models.IntegerField()

    rol = models.CharField(max_length=10, choices=ROLES_MENSAJE)
    tipo = models.CharField(max_length=15, choices=TIPOS_MENSAJE, default="texto")

    cuerpo = models.TextField(blank=True, default="")
    nombre_herramienta = models.CharField(max_length=40, blank=True, default="")
    # Cuando tipo='accion': el preview/confirm vive en un Dictado auditado.
    dictado = models.ForeignKey(
        "el_dictado.Dictado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mensajes_chat",
    )
    chalan = models.CharField(max_length=30, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "el_dictado_mensaje_chat"
        indexes = [
            models.Index(fields=["conversacion", "orden"]),
        ]
        ordering = ["conversacion", "orden"]

    def __str__(self) -> str:
        return f"msg#{self.pk} {self.rol}/{self.tipo} conv={self.conversacion_id}"
