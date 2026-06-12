"""Visita — marca puntual "estuve aquí" vinculada a cliente o proveedor."""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPO_VISITA = (
    ("cliente", "Cliente"),
    ("proveedor", "Proveedor"),
    ("otro", "Otro"),
)


class Visita(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="visitas_checador",
    )
    jornada = models.ForeignKey(
        "checador.Jornada", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitas",
    )

    registrado_en = models.DateTimeField(help_text="Hora del dispositivo")
    recibido_en = models.DateTimeField(auto_now_add=True, help_text="Hora del servidor")

    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True, help_text="Metros")
    sin_geo = models.BooleanField(default=False)
    capturada_offline = models.BooleanField(default=False)
    # uuid generado en el cliente — el endpoint de sync es idempotente por él.
    uuid_cliente = models.CharField(max_length=64, blank=True, default="", db_index=True)

    tipo = models.CharField(max_length=10, choices=TIPO_VISITA, default="cliente")
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitas_checador",
    )
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitas_checador",
    )
    nota = models.TextField(blank=True, default="")

    class Meta:
        db_table = "checador_visita"
        ordering = ["-registrado_en"]
        indexes = [
            models.Index(fields=["usuario", "registrado_en"]),
            models.Index(fields=["uuid_cliente"]),
        ]

    def __str__(self) -> str:
        return f"Visita {self.usuario_id} · {self.tipo} · {self.registrado_en:%Y-%m-%d %H:%M}"

    @property
    def destino(self) -> str:
        if self.cliente_id:
            return getattr(self.cliente, "razon_social", "Cliente")
        if self.proveedor_id:
            return getattr(self.proveedor, "razon_social", "Proveedor")
        return self.nota or "Otro"

    @property
    def maps_url(self) -> str:
        if self.lat is not None and self.lng is not None:
            return f"https://maps.google.com/?q={self.lat},{self.lng}"
        return ""
