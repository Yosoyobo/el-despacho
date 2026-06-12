"""Reconciliación bancaria (S3 resto).

`ConciliacionBancaria` representa el cotejo del estado de cuenta de un
banco (cuenta contable con slot `banco`/`stripe_saldo`/`mp_saldo`...)
contra los movimientos del libro en esa cuenta, para un rango de fechas.

`LineaBancaria` es cada renglón del estado de cuenta importado (CSV). El
`monto` es **firmado**: positivo = dinero que ENTRA al banco (cargo a la
cuenta deudora `banco`), negativo = dinero que SALE. El cotejo marca cada
línea como conciliada y, opcionalmente, la liga a una `Partida` del libro.

V1: importar CSV + auto-match por monto+fecha + match/unmatch manual +
resumen (saldo banco vs saldo libros + pendientes de ambos lados). NO
genera asientos automáticos por comisiones bancarias (eso se captura con
el wizard de movimiento existente).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

ESTADO_CONCILIACION = (
    ("abierta", "Abierta"),
    ("cerrada", "Cerrada"),
)


class ConciliacionBancaria(models.Model):
    cuenta = models.ForeignKey(
        "contaduria.CuentaContable", on_delete=models.PROTECT,
        related_name="conciliaciones",
    )
    desde = models.DateField(db_index=True)
    hasta = models.DateField(db_index=True)

    # Saldo final que reporta el estado de cuenta del banco (lo teclea el
    # usuario al crear la conciliación). La diferencia contra el saldo de
    # libros es el indicador clave de la reconciliación.
    saldo_estado_cuenta = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
    )

    estado = models.CharField(
        max_length=10, choices=ESTADO_CONCILIACION, default="abierta", db_index=True,
    )

    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="conciliaciones_creadas",
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contaduria_conciliacion_bancaria"
        ordering = ["-hasta", "-creada_en"]

    def __str__(self) -> str:
        return f"Conciliación {self.cuenta.codigo} {self.desde}→{self.hasta}"


class LineaBancaria(models.Model):
    conciliacion = models.ForeignKey(
        ConciliacionBancaria, on_delete=models.CASCADE, related_name="lineas",
    )
    fecha = models.DateField(db_index=True)
    descripcion = models.CharField(max_length=300, blank=True, default="")
    referencia = models.CharField(max_length=80, blank=True, default="")

    # Firmado: + entra al banco / − sale del banco.
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    conciliada = models.BooleanField(default=False, db_index=True)
    # Partida del libro (en la cuenta `banco`) con la que cuadró esta línea.
    partida = models.ForeignKey(
        "contaduria.Partida", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lineas_bancarias",
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "contaduria_linea_bancaria"
        ordering = ["conciliacion", "fecha", "orden", "pk"]
        indexes = [
            models.Index(fields=["conciliacion", "conciliada"]),
        ]

    def __str__(self) -> str:
        signo = "+" if self.monto >= 0 else "−"
        return f"{self.fecha} {signo}{abs(self.monto)} {self.descripcion[:40]}"
