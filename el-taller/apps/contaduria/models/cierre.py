"""Cierre de periodo contable (S3 resto).

Un `CierrePeriodo` cancela las cuentas de resultado (ingresos 4.x y
egresos 5.x) del rango contra `3.2.02 Utilidad del ejercicio`, dejando
sus saldos en cero para arrancar el siguiente periodo. El asiento de
cierre (origen=`cierre`) lo arma `services.cerrar_periodo`.

Reversible: `reabrir` anula el asiento y marca el cierre como reabierto
(no se borra, queda la traza). Idempotente por `referencia_externa` del
asiento (`contaduria.cierre:<desde>:<hasta>`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models


class CierrePeriodoVigentesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(reabierto=False)


class CierrePeriodo(models.Model):
    desde = models.DateField(db_index=True)
    hasta = models.DateField(db_index=True)

    # Asiento de cierre generado. SET_NULL para no perder la traza del
    # cierre si el asiento se borrara por alguna razón externa.
    asiento = models.ForeignKey(
        "contaduria.Asiento", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cierres",
    )
    utilidad = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cierres_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    reabierto = models.BooleanField(default=False, db_index=True)
    reabierto_en = models.DateTimeField(null=True, blank=True)
    reabierto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cierres_reabiertos",
    )
    motivo_reapertura = models.CharField(max_length=300, blank=True, default="")

    objects = models.Manager()
    vigentes = CierrePeriodoVigentesManager()

    class Meta:
        db_table = "contaduria_cierre_periodo"
        ordering = ["-hasta", "-creado_en"]
        indexes = [
            models.Index(fields=["-hasta", "-creado_en"]),
        ]

    def __str__(self) -> str:
        return f"Cierre {self.desde} → {self.hasta}"

    @property
    def referencia(self) -> str:
        return f"contaduria.cierre:{self.desde.isoformat()}:{self.hasta.isoformat()}"

    @staticmethod
    def referencia_para(desde: date, hasta: date) -> str:
        return f"contaduria.cierre:{desde.isoformat()}:{hasta.isoformat()}"
