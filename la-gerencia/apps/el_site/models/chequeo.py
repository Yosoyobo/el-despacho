from django.db import models


class SiteChequeo(models.Model):
    """Lectura puntual del estado de una plataforma. Una fila por chequeo
    (manual o diario). Se consulta por ``ordering = -probado_en``."""

    ESTADOS = (
        ("ok", "OK"),
        ("error", "Error"),
        ("no_configurada", "No configurada"),
    )
    ORIGENES = (
        ("diario", "Diario"),
        ("manual", "Manual"),
    )

    plataforma = models.CharField(max_length=40, db_index=True)
    estado = models.CharField(max_length=20, choices=ESTADOS)
    latencia_ms = models.IntegerField(null=True, blank=True)
    mensaje_error = models.TextField(null=True, blank=True)
    origen = models.CharField(max_length=10, choices=ORIGENES)
    actor_email = models.EmailField(null=True, blank=True)
    probado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "site_chequeo"
        ordering = ["-probado_en"]
        indexes = [
            models.Index(fields=["plataforma", "-probado_en"]),
        ]

    def __str__(self) -> str:
        return f"{self.plataforma}:{self.estado}@{self.probado_en.isoformat()}"
