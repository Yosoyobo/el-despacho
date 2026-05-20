from django.conf import settings
from django.db import models


class EgresoOcrLog(models.Model):
    """Registro técnico de cada OCR procesado (DOC_06 §4.4).

    Activación pipeline OCR: S2b.3b (requiere Google Drive wrapper funcional).
    El modelo + tabla quedan en V1 para que el módulo OCR se enchufe sin
    nuevas migraciones cuando Drive esté listo."""

    egreso = models.ForeignKey(
        "tesoreria.Egreso", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ocr_logs",
    )

    drive_file_id = models.CharField(max_length=100, blank=True, default="")
    nombre_original = models.CharField(max_length=300, blank=True, default="")
    tamano_original_bytes = models.BigIntegerField(default=0)
    tamano_optimizado_bytes = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True, default="")

    chalan_usado = models.CharField(max_length=30, blank=True, default="")
    modelo = models.CharField(max_length=80, blank=True, default="")
    raw_extraccion = models.JSONField(default=dict, blank=True)

    latencia_ms = models.IntegerField(default=0)
    costo_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    fue_corregido = models.BooleanField(default=False)
    correcciones = models.JSONField(default=dict, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ocr_logs_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tesoreria_egreso_ocr_log"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["-creado_en"]),
            models.Index(fields=["egreso"]),
        ]
