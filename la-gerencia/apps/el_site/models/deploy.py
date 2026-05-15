from django.db import models


class SiteDeploy(models.Model):
    """Registro de cada deploy de La Mudanza. Lo escribe el comando
    ``notificar_deploy`` desde el container al final del SSH script."""

    ESTADOS = (("ok", "OK"), ("rollback", "Rollback"))

    estado = models.CharField(max_length=10, choices=ESTADOS)
    commit = models.CharField(max_length=64, blank=True, default="")
    nota = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "site_deploy"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"{self.estado}:{self.commit[:8]}@{self.creado_en.isoformat()}"
