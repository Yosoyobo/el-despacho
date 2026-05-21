"""Asientos contables y partidas — partida doble.

Cada `Asiento` tiene N `Partida`s. La suma de cargos == suma de abonos
(invariante de partida doble). Validado en `services.crear_asiento`.

Cada partida tiene exactamente uno de `cargo` o `abono` distinto de 0.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

ORIGEN_ASIENTO = (
    ("manual", "Captura manual"),
    ("auto_ingreso", "Automático · ingreso Tesorería"),
    ("auto_egreso", "Automático · egreso Tesorería"),
    ("auto_anulacion_ingreso", "Automático · anulación ingreso"),
    ("auto_anulacion_egreso", "Automático · anulación egreso"),
    ("auto_factura_emitida", "Automático · factura emitida"),
    ("auto_factura_cancelada", "Automático · factura cancelada"),
    ("auto_reembolso", "Automático · reembolso a empleado"),
    ("ajuste", "Ajuste contable"),
    ("cierre", "Cierre de periodo"),
)


def _generar_codigo_asiento(anio: int) -> str:
    """AST-YYYY-NNNN tomando el max correlativo del año. Usar bajo transaction.atomic."""
    prefijo = f"AST-{anio}-"
    ultimo = (
        Asiento.objects.select_for_update()
        .filter(codigo__startswith=prefijo)
        .order_by("-codigo")
        .first()
    )
    if ultimo:
        try:
            n = int(ultimo.codigo.rsplit("-", 1)[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefijo}{n:04d}"


class AsientoNoAnuladoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(anulado=False)


class Asiento(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    fecha = models.DateField(default=date.today, db_index=True)
    descripcion = models.CharField(max_length=300)

    origen = models.CharField(max_length=30, choices=ORIGEN_ASIENTO, default="manual", db_index=True)

    # Referencia genérica como string para evitar GenericForeignKey:
    # "tesoreria.ingreso:42" / "tesoreria.egreso:17" / "cotizaciones.cotizacion:5".
    # Permite idempotencia: si ya existe asiento con esta referencia, no
    # se vuelve a crear (manejado en services).
    referencia_externa = models.CharField(max_length=120, blank=True, default="", db_index=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="asientos_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    anulado = models.BooleanField(default=False, db_index=True)
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="asientos_anulados",
    )
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    objects = models.Manager()
    vigentes = AsientoNoAnuladoManager()

    class Meta:
        db_table = "contaduria_asiento"
        ordering = ["-fecha", "-creado_en"]
        indexes = [
            models.Index(fields=["-fecha", "-creado_en"]),
            models.Index(fields=["origen", "-fecha"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.descripcion[:60]}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            anio = (self.fecha or date.today()).year
            with transaction.atomic():
                self.codigo = _generar_codigo_asiento(anio)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @property
    def total(self) -> Decimal:
        """Suma de cargos == suma de abonos (deben ser iguales en partida doble)."""
        from django.db.models import Sum
        s = self.partidas.aggregate(c=Sum("cargo"))["c"]
        return s or Decimal("0.00")


class Partida(models.Model):
    asiento = models.ForeignKey(Asiento, on_delete=models.CASCADE, related_name="partidas")
    cuenta = models.ForeignKey(
        "contaduria.CuentaContable", on_delete=models.PROTECT, related_name="partidas",
    )
    orden = models.PositiveIntegerField(default=0)

    cargo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    abono = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    descripcion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "contaduria_partida"
        ordering = ["asiento", "orden", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cargo__gte=0) & models.Q(abono__gte=0),
                name="contaduria_partida_montos_no_negativos",
            ),
        ]
        indexes = [
            models.Index(fields=["cuenta"]),
        ]

    def __str__(self) -> str:
        m = self.cargo if self.cargo > 0 else self.abono
        lado = "D" if self.cargo > 0 else "H"
        return f"{self.cuenta.codigo} {lado} {m}"
