from __future__ import annotations

from django.conf import settings
from django.db import models

from .recado import Recado


class RecadoAdjunto(models.Model):
    """Archivo adjunto a un recado legacy, almacenado en Google Drive.

    Guardamos solo la referencia (`drive_file_id`); el contenido se sirve a
    usuarios autenticados vía el proxy de El Despacho, no con liga pública.
    """

    recado = models.ForeignKey(
        Recado, on_delete=models.CASCADE, related_name="adjuntos"
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
        related_name="recado_adjuntos",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recado_adjunto"
        ordering = ["creado_en"]

    def __str__(self) -> str:
        return f"adjunto#{self.pk} {self.nombre}"

    @property
    def es_imagen(self) -> bool:
        return self.mime_type.startswith("image/")
