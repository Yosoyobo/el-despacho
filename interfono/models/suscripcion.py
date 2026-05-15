from __future__ import annotations

from django.conf import settings
from django.db import models


class InterfonoSuscripcion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suscripciones_push",
    )
    endpoint = models.URLField(max_length=2000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=200)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    desactivada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interfono_suscripcion"
        indexes = [
            models.Index(fields=["usuario", "activa"]),
        ]
        ordering = ["-creada_en"]

    def __str__(self) -> str:
        return f"suscripcion#{self.pk} u={self.usuario_id} activa={self.activa}"

    def etiqueta_dispositivo(self) -> str:
        ua = (self.user_agent or "").lower()
        navegador = "Navegador"
        for clave, label in (
            ("firefox", "Firefox"),
            ("edg/", "Edge"),
            ("chrome", "Chrome"),
            ("safari", "Safari"),
        ):
            if clave in ua:
                navegador = label
                break
        plataforma = "dispositivo"
        for clave, label in (
            ("iphone", "iPhone"),
            ("ipad", "iPad"),
            ("android", "Android"),
            ("mac os", "Mac"),
            ("macintosh", "Mac"),
            ("windows", "Windows"),
            ("linux", "Linux"),
        ):
            if clave in ua:
                plataforma = label
                break
        return f"{navegador} en {plataforma}"
