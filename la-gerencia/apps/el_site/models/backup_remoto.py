from django.db import models


class SiteBackupRemoto(models.Model):
    """Registro de cada `rsync` saliente de `archivo.sh` hacia HAL (o
    cualquier destino off-site futuro). El comando management
    ``registrar_backup_remoto`` escribe aquí."""

    ESTADOS = (("ok", "OK"), ("error", "Error"))

    archivo = models.CharField(max_length=240)
    destino = models.CharField(max_length=80, default="HAL")
    estado = models.CharField(max_length=10, choices=ESTADOS)
    tamano_bytes = models.BigIntegerField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "site_backup_remoto"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"{self.destino}:{self.archivo}:{self.estado}"
