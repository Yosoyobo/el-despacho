"""La Nómina interna — sueldo fijo quincenal (S-Checador-V2, decisiones de Oscar 2026-09-29).

Lo que es y lo que NO es:

- **Sueldo fijo por quincena** (1–15 y 16–fin de mes). Las horas del Checador
  sólo INFORMAN: el recibo muestra horas, retardos y faltas, pero el sueldo no
  cambia solo. Quien cierra decide y ajusta a mano con un concepto.
- **Sólo reporte.** No crea egresos ni asientos. La única escritura hacia afuera
  es saldar en Tesorería los reembolsos que el recibo incluyó, al marcarlo
  pagado (para no pagarlos dos veces).
- **No calcula impuestos** (§4 #16): si el contador pasa retenciones, se
  capturan como deducción.

Modelos:

- `SueldoPersona` — sueldo quincenal con fecha de vigencia. El vigente para una
  fecha es el de mayor `vigente_desde <= fecha`. Un renglón con
  `en_nomina=False` es la baja: desde esa fecha la persona ya no cobra.
- `PeriodoNomina` — una quincena: abierto → calculado → cerrado.
- `ReciboNomina` — uno por persona y quincena. Copia el sueldo aplicado (un
  aumento posterior no lo toca) y las horas del periodo. por_pagar → pagado.
- `ConceptoRecibo` — percepciones y deducciones (bono, abono a préstamo,
  reembolso, deducción libre, ajuste).
- `PrestamoNomina` — préstamos/adelantos que se descuentan quincena a quincena.
  El saldo baja SÓLO cuando se cierra la quincena que trae el abono.
"""

from __future__ import annotations

import calendar
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

CERO = Decimal("0.00")

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def quincena_de(fecha: datetime.date) -> tuple[datetime.date, datetime.date]:
    """(inicio, fin) de la quincena que contiene `fecha`: 1–15 o 16–último día."""
    if fecha.day <= 15:
        return fecha.replace(day=1), fecha.replace(day=15)
    ultimo = calendar.monthrange(fecha.year, fecha.month)[1]
    return fecha.replace(day=16), fecha.replace(day=ultimo)


def etiqueta_quincena(inicio: datetime.date) -> str:
    """«1ª quincena de septiembre 2026» / «2ª quincena de …»."""
    cual = "1ª" if inicio.day <= 15 else "2ª"
    return f"{cual} quincena de {MESES[inicio.month - 1]} {inicio.year}"


class SueldoPersona(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sueldos_nomina",
    )
    sueldo_quincenal = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(CERO)],
        help_text="Lo que cobra por quincena, antes de conceptos.",
    )
    vigente_desde = models.DateField(
        help_text="Desde qué día aplica. Lo más claro es el 1 o el 16.",
    )
    en_nomina = models.BooleanField(
        default=True,
        help_text="Apagado = baja: desde esta fecha la persona ya no cobra por nómina.",
    )
    notas = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sueldos_nomina_capturados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_sueldo_persona"
        ordering = ["usuario_id", "-vigente_desde"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "vigente_desde"], name="checador_sueldo_usuario_desde",
            ),
        ]

    def __str__(self) -> str:
        return f"Sueldo {self.usuario_id} · ${self.sueldo_quincenal} desde {self.vigente_desde}"


ESTADO_PERIODO = (
    ("abierto", "Abierto"),
    ("calculado", "Calculado"),
    ("cerrado", "Cerrado"),
)


class PeriodoNomina(models.Model):
    fecha_inicio = models.DateField(unique=True)
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADO_PERIODO, default="abierto")
    notas = models.TextField(blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_nomina_creados",
    )
    calculado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_nomina_calculados",
    )
    calculado_en = models.DateTimeField(null=True, blank=True)
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_nomina_cerrados",
    )
    cerrado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_periodo_nomina"
        ordering = ["-fecha_inicio"]

    def __str__(self) -> str:
        return self.etiqueta

    @property
    def etiqueta(self) -> str:
        return etiqueta_quincena(self.fecha_inicio)

    @property
    def cerrado(self) -> bool:
        return self.estado == "cerrado"

    @property
    def editable(self) -> bool:
        return self.estado != "cerrado"


ESTADO_RECIBO = (
    ("por_pagar", "Por pagar"),
    ("pagado", "Pagado"),
)


class ReciboNomina(models.Model):
    periodo = models.ForeignKey(PeriodoNomina, on_delete=models.CASCADE, related_name="recibos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recibos_nomina",
    )

    # Copia del sueldo que aplicó: un aumento posterior NO toca este recibo.
    sueldo_aplicado = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    sueldo_vigente_desde = models.DateField(null=True, blank=True)
    # Si el sueldo cambió dentro de la quincena, qué había antes (para el aviso).
    sueldo_anterior = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Lo que informa El Checador (NO mueve el sueldo).
    dias_laborales = models.PositiveSmallIntegerField(default=0)
    horas_esperadas = models.DecimalField(max_digits=7, decimal_places=2, default=CERO)
    horas_trabajadas = models.DecimalField(max_digits=7, decimal_places=2, default=CERO)
    retardos = models.PositiveSmallIntegerField(default=0)
    minutos_retardo = models.PositiveIntegerField(default=0)
    faltas = models.PositiveSmallIntegerField(default=0)

    percepciones = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    deducciones = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    neto = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)

    estado = models.CharField(max_length=10, choices=ESTADO_RECIBO, default="por_pagar")
    pagado_en = models.DateField(null=True, blank=True, help_text="Fecha real del depósito.")
    pagado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recibos_nomina_marcados",
    )
    pago_registrado_en = models.DateTimeField(null=True, blank=True)
    metodo_pago = models.CharField(max_length=30, blank=True, default="")

    # Lo automático que alguien quitó a mano ("prestamo:<pk>", "egreso:<pk>"):
    # recalcular no lo vuelve a proponer.
    quitados = models.JSONField(default=list, blank=True)
    notas = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_recibo_nomina"
        ordering = ["periodo_id", "usuario__nombre_completo"]
        constraints = [
            models.UniqueConstraint(fields=["periodo", "usuario"], name="checador_recibo_periodo_usuario"),
        ]

    def __str__(self) -> str:
        return f"Recibo {self.usuario_id} · {self.periodo}"

    @property
    def cerrado(self) -> bool:
        return self.periodo.cerrado

    @property
    def editable(self) -> bool:
        return self.periodo.editable

    @property
    def pagado(self) -> bool:
        return self.estado == "pagado"

    @property
    def cambio_sueldo_en_periodo(self) -> bool:
        """El sueldo que aplica empezó a media quincena (aviso para ajustar)."""
        return bool(
            self.sueldo_vigente_desde
            and self.sueldo_vigente_desde > self.periodo.fecha_inicio
        )


TIPO_CONCEPTO = (
    ("percepcion", "Percepción"),
    ("deduccion", "Deducción"),
)

CLASE_CONCEPTO = (
    ("bono", "Bono / comisión"),
    ("prestamo", "Abono a préstamo"),
    ("reembolso", "Reembolso"),
    ("deduccion", "Deducción"),
    ("ajuste", "Ajuste"),
)

# El tipo que manda cada clase (el ajuste puede ir de los dos lados).
TIPO_POR_CLASE = {
    "bono": "percepcion",
    "reembolso": "percepcion",
    "prestamo": "deduccion",
    "deduccion": "deduccion",
}


class ConceptoRecibo(models.Model):
    recibo = models.ForeignKey(ReciboNomina, on_delete=models.CASCADE, related_name="conceptos")
    tipo = models.CharField(max_length=10, choices=TIPO_CONCEPTO)
    clase = models.CharField(max_length=10, choices=CLASE_CONCEPTO)
    descripcion = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(CERO)])
    nota = models.TextField(blank=True, default="")

    prestamo = models.ForeignKey(
        "checador.PrestamoNomina", on_delete=models.PROTECT, null=True, blank=True,
        related_name="abonos",
    )
    egreso = models.ForeignKey(
        "tesoreria.Egreso", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conceptos_nomina",
    )
    # Lo propuso el cálculo (abono, reembolso). Si alguien lo edita a mano deja de
    # serlo y recalcular lo respeta.
    automatico = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=100)

    class Meta:
        db_table = "checador_concepto_recibo"
        ordering = ["orden", "id"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.descripcion} ${self.monto}"

    @property
    def clave_automatica(self) -> str:
        if self.prestamo_id:
            return f"prestamo:{self.prestamo_id}"
        if self.egreso_id:
            return f"egreso:{self.egreso_id}"
        return ""


class PrestamoNomina(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prestamos_nomina",
    )
    concepto = models.CharField(max_length=160, default="Préstamo")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha = models.DateField()
    # Cuánto se descuenta cada quincena. Si se capturó por número de quincenas,
    # la cuota sale de monto ÷ quincenas (el último abono se ajusta al saldo).
    cuota = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    quincenas = models.PositiveSmallIntegerField(null=True, blank=True)
    # Baja SÓLO al cerrar la quincena que trae el abono.
    saldo = models.DecimalField(max_digits=12, decimal_places=2)
    notas = models.TextField(blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prestamos_nomina_capturados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_prestamo_nomina"
        ordering = ["-fecha", "-id"]

    def __str__(self) -> str:
        return f"Préstamo {self.usuario_id} · ${self.monto} (saldo ${self.saldo})"

    @property
    def saldado(self) -> bool:
        return self.saldo <= CERO
