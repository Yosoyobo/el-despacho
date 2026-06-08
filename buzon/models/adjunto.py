from __future__ import annotations

from django.conf import settings
from django.db import models

from .mensaje_interno import MensajeBuzon


class MensajeBuzonAdjunto(models.Model):
    """Archivo adjunto a un mensaje del Buzón, almacenado en Google Drive.

    Igual patrón que RecadoAdjunto/MensajeAdjunto: guardamos la referencia y
    servimos el contenido por proxy autenticado, no con liga pública.
    """

    mensaje = models.ForeignKey(
        MensajeBuzon, on_delete=models.CASCADE, related_name="adjuntos"
    )
    drive_file_id = models.CharField(max_length=255)
    nombre = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True, default="")
    tamano_bytes = models.PositiveBigIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buzon_adjuntos",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buzon_mensaje_adjunto"
        ordering = ["creado_en"]

    def __str__(self) -> str:
        return f"buzon_adjunto#{self.pk} {self.nombre}"

    @property
    def es_imagen(self) -> bool:
        return self.mime_type.startswith("image/")
