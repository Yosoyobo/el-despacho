"""Campañas de correo masivo (S-LC-Feedback-V6 Bloque 7C).

Auditoría completa: una `CampanaCorreo` por lote y un `CampanaEnvio` por
destinatario (patrón `facturacion.RecordatorioCobranza`). El envío es
best-effort: un destinatario fallido no aborta el lote.
"""

from django.conf import settings
from django.db import models

ESTADOS_ENVIO = (
    ("enviado", "Enviado"),
    ("fallido", "Fallido"),
)


class CampanaCorreo(models.Model):
    plantilla_slug = models.CharField(max_length=40)
    asunto_custom = models.CharField(max_length=200, blank=True, default="")
    mensaje_custom = models.TextField(blank=True, default="")
    total_destinatarios = models.PositiveIntegerField(default=0)
    enviados = models.PositiveIntegerField(default=0)
    fallidos = models.PositiveIntegerField(default=0)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="campanas_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "campanas_correo"
        ordering = ["-creado_en"]
        verbose_name = "campaña de correo"
        verbose_name_plural = "campañas de correo"

    def __str__(self):
        return f"Campaña {self.pk} · {self.plantilla_slug} · {self.enviados}/{self.total_destinatarios}"


class CampanaEnvio(models.Model):
    campana = models.ForeignKey(CampanaCorreo, on_delete=models.CASCADE, related_name="envios")
    cliente = models.ForeignKey("cartera.Cliente", on_delete=models.PROTECT, related_name="envios_campana")
    email = models.EmailField()
    estado = models.CharField(max_length=10, choices=ESTADOS_ENVIO, default="enviado")
    error = models.CharField(max_length=300, blank=True, default="")
    enviado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "campanas_envio"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.email} ({self.estado})"
