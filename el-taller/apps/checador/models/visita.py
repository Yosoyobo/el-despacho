"""Visita — marca puntual "estuve aquí" vinculada a cliente o proveedor."""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPO_VISITA = (
    ("cliente", "Cliente"),
    ("proveedor", "Proveedor"),
    ("contacto", "Contacto"),
    ("otro", "Otro"),
)

# Qué fue a hacer la persona al POI (S-Checador-V14). Lo distingue de `tipo`
# (a quién). El Chalán puede inferirlo de la nota/evidencia para no depender de
# que el runner lo marque (ver `apps.checador.verificacion`).
PROPOSITO_VISITA = (
    ("visita", "Visita"),
    ("tarea", "Tarea/entrega completada"),
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
    contacto = models.ForeignKey(
        "cartera.ClienteContacto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitas_checador",
    )
    # Tarea opcional que el registro completa (p. ej. "recoger muestras"). Permite
    # que El Chalán verifique contra el pendiente asignado.
    tarea = models.ForeignKey(
        "pizarron.Tarea", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="visitas_checador",
    )
    proposito = models.CharField(max_length=10, choices=PROPOSITO_VISITA, default="visita")
    nota = models.TextField(blank=True, default="")

    # Verificación por El Chalán (S-Checador-V14). El AI clasifica el propósito y
    # valora si la tarea quedó cumplida, para no depender de que el runner lo
    # marque. Best-effort; si no corre, los campos quedan vacíos/None.
    ia_proposito = models.CharField(max_length=10, blank=True, default="")
    ia_completada = models.BooleanField(null=True, blank=True)
    ia_confianza = models.FloatField(null=True, blank=True)
    ia_resumen = models.TextField(blank=True, default="")
    ia_verificado_en = models.DateTimeField(null=True, blank=True)

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
        if self.contacto_id:
            nombre = getattr(self.contacto, "nombre", "Contacto")
            cli = getattr(getattr(self.contacto, "cliente", None), "razon_social", "")
            return f"{nombre} ({cli})" if cli else nombre
        if self.cliente_id:
            return getattr(self.cliente, "razon_social", "Cliente")
        if self.proveedor_id:
            return getattr(self.proveedor, "razon_social", "Proveedor")
        return self.nota or "Otro"

    @property
    def proposito_efectivo(self) -> str:
        """Propósito confirmado por el AI si lo hay; si no, el que se marcó."""
        return self.ia_proposito or self.proposito

    @property
    def maps_url(self) -> str:
        if self.lat is not None and self.lng is not None:
            return f"https://maps.google.com/?q={self.lat},{self.lng}"
        return ""
