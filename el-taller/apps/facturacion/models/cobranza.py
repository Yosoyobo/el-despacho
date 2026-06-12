"""RecordatorioCobranza — auditoría de los recordatorios de pago enviados.

Una fila por recordatorio enviado (o intentado) para una factura. Sirve
para no spamear (cadencia en `ajustes.ConfiguracionCobranza`) y para que
el equipo vea en el detalle de la factura cuándo se le recordó al cliente.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class RecordatorioCobranza(models.Model):
    factura = models.ForeignKey(
        "facturacion.Factura", on_delete=models.CASCADE, related_name="recordatorios",
    )
    enviado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    # Tipo de recordatorio: pre-vencimiento o por mora.
    tipo = models.CharField(max_length=20, default="mora")  # "mora" | "pre_vencimiento"
    canal = models.CharField(max_length=10, blank=True, default="")  # "smtp" | "n8n"
    destinatario = models.EmailField(blank=True, default="")
    dias_vencida = models.IntegerField(default=0)
    saldo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    ok = models.BooleanField(default=False)
    detalle = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "facturacion_recordatorio_cobranza"
        ordering = ["-enviado_en"]
        indexes = [
            models.Index(fields=["factura", "-enviado_en"]),
        ]

    def __str__(self) -> str:
        return f"Recordatorio {self.factura_id} · {self.enviado_en:%Y-%m-%d}"
