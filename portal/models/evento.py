"""EventoPortal — la bitácora de lo que pasa en La Recepción.

Existe para contestar dos preguntas: «¿quién aprobó esto y desde dónde?» y
«¿alguien está tanteando el portal?». Guarda la dirección y el navegador como
REFERENCIA (no son prueba de identidad) y no sale de esta tabla: no hay pantalla
que la muestre ni evento que la mande fuera. Nunca debe ser el motivo de que
algo falle: `portal.servicios.registrar_evento` no lanza.
"""

from __future__ import annotations

from django.db import models

TIPOS_EVENTO = (
    ("invitado", "Invitado por el despacho"),
    ("revocado", "Acceso revocado"),
    ("enlace", "Pidió un enlace de entrada"),
    ("entrada", "Entró"),
    ("salida", "Salió"),
    ("descarga", "Descargó un documento"),
    ("aprobacion", "Aprobó una cotización"),
    ("rechazo", "Rechazó una cotización"),
)


class EventoPortal(models.Model):
    acceso = models.ForeignKey(
        "portal.AccesoCliente", on_delete=models.CASCADE, related_name="eventos",
    )
    tipo = models.CharField(max_length=12, choices=TIPOS_EVENTO, db_index=True)
    detalle = models.CharField(max_length=300, blank=True, default="")
    ip = models.CharField(max_length=64, blank=True, default="")
    agente = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_evento"
        verbose_name = "evento del portal"
        verbose_name_plural = "eventos del portal"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"{self.tipo} · acceso {self.acceso_id}"
