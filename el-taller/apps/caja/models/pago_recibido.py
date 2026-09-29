"""PagoRecibido — lo que una pasarela avisó por webhook FIRMADO.

Una fila por pago EN LA PASARELA (`pasarela` + `id_externo` es único): el mismo
aviso repetido —y Stripe y MercadoPago repiten— encuentra su fila y no vuelve a
crear el ingreso. Es la idempotencia del sistema, en la base y no en la memoria.

`payload` guarda lo MÍNIMO para rastrear el pago (ids, estado, monto, moneda,
tipo de método). Nunca datos de tarjeta ni del pagador: el cobro lo hizo la
pasarela y ahí se quedan.

Estados:
  · `registrado`  — se creó el ingreso (y se cobró la factura, si era una).
  · `por_revisar` — llegó dinero que NO cuadra (monto distinto, factura ya
    cobrada, link anulado o vencido…). No se registra solo: alguien decide.
  · `pendiente`   — la pasarela lo recibió pero aún no lo acredita (OXXO, SPEI).
  · `rechazado`   — la pasarela lo rechazó o lo canceló.
  · `descartado`  — alguien lo revisó y decidió no registrarlo (p. ej. se devolvió).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

PASARELAS = (
    ("stripe", "Stripe"),
    ("mercadopago", "MercadoPago"),
)

ESTADOS_PAGO = (
    ("registrado", "Registrado"),
    ("por_revisar", "Por revisar"),
    ("pendiente", "Pendiente de acreditar"),
    ("rechazado", "Rechazado"),
    ("descartado", "Descartado"),
)

# Estados finales: un aviso nuevo del mismo pago ya no cambia nada.
ESTADOS_CERRADOS = {"registrado", "por_revisar", "descartado"}


class PagoRecibido(models.Model):
    pasarela = models.CharField(max_length=12, choices=PASARELAS)
    id_externo = models.CharField(max_length=120)

    link = models.ForeignKey(
        "caja.LinkPago", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pagos",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=3, default="MXN")
    fecha_pago = models.DateTimeField(null=True, blank=True)

    estado = models.CharField(max_length=12, choices=ESTADOS_PAGO, db_index=True)
    # Lo que dijo la pasarela, tal cual (paid, approved, pending, …).
    estado_pasarela = models.CharField(max_length=40, blank=True, default="")
    # Por qué quedó por revisar (o por qué se descartó).
    motivo = models.CharField(max_length=300, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    ingreso = models.ForeignKey(
        "tesoreria.Ingreso", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pagos_en_linea",
    )

    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pagos_en_linea_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    nota_revision = models.CharField(max_length=300, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "caja_pago_recibido"
        ordering = ["-creado_en"]
        verbose_name = "pago recibido en línea"
        verbose_name_plural = "pagos recibidos en línea"
        constraints = [
            models.UniqueConstraint(fields=["pasarela", "id_externo"], name="caja_pago_unico_por_pasarela"),
        ]
        indexes = [models.Index(fields=["estado", "-creado_en"])]

    def __str__(self) -> str:
        return f"PagoRecibido({self.pasarela}:{self.id_externo}, ${self.monto}, {self.estado})"

    @property
    def cerrado(self) -> bool:
        return self.estado in ESTADOS_CERRADOS
