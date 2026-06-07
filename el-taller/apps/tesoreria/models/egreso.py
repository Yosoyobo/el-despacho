from datetime import date

from django.conf import settings
from django.db import models, transaction

from .centro_de_costo import CentroDeCosto

ESTADOS_PAGO = (
    ("pagado", "Pagado (saldado)"),
    ("por_reembolsar", "Por reembolsar al empleado"),
    ("pendiente", "Pendiente de pago"),
)

METODOS_EGRESO = (
    ("transferencia", "Transferencia empresa"),
    ("tarjeta_empresa", "Tarjeta empresa"),
    ("tarjeta_personal", "Tarjeta personal (reembolso)"),
    ("efectivo", "Efectivo"),
    ("cheque", "Cheque"),
    ("otro", "Otro"),
)

ORIGEN_EGRESO = (
    ("manual", "Captura manual"),
    ("ocr", "OCR de recibo"),
    ("dictado", "Dictado El Chalán"),
    ("sala_juntas", "Dictado desde Sala de Juntas"),
)


class EgresoNoAnuladoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(anulado=False)


class Egreso(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    # Desglose IVA (S-LC-Buzon). Ver Ingreso.subtotal/incluye_iva.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incluye_iva = models.BooleanField(default=False)
    moneda = models.CharField(max_length=3, default="MXN")
    fecha = models.DateField()

    descripcion = models.CharField(max_length=300)
    # Proveedor del catálogo (S-LC-Buzon). Null = "Gasto operativo" (viáticos,
    # operación interna). `proveedor_nombre` se mantiene denormalizado para
    # exports/display y se rellena desde el proveedor o "Gasto operativo".
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos",
    )
    proveedor_nombre = models.CharField(max_length=200, blank=True, default="")

    centro_de_costo = models.ForeignKey(
        CentroDeCosto, on_delete=models.PROTECT, related_name="egresos",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos",
    )

    pagado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos_que_pague",
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos_que_solicite",
    )

    estado_pago = models.CharField(max_length=20, choices=ESTADOS_PAGO, default="pagado", db_index=True)
    metodo = models.CharField(max_length=30, choices=METODOS_EGRESO, default="transferencia")

    # Registro del pago efectivo (sprint S-Finanzas-V2). Cuando el egreso
    # se reembolsa via tesoreria.services.reembolsar_egreso, estos campos
    # registran la fecha y de qué cuenta (banco/caja) salió el dinero.
    # Null cuando el egreso todavía no se ha pagado.
    pagado_en = models.DateField(null=True, blank=True, db_index=True)
    pagado_desde = models.CharField(
        max_length=20, blank=True, default="",
        choices=(("", "—"), ("banco", "Banco"), ("caja", "Caja")),
        help_text="De qué cuenta salió el dinero al ejecutar el pago.",
    )

    drive_file_id = models.CharField(max_length=100, blank=True, default="")
    drive_url_view = models.URLField(max_length=500, blank=True, default="")
    drive_url_thumbnail = models.URLField(max_length=500, blank=True, default="")
    tiene_comprobante = models.BooleanField(default=False)

    origen = models.CharField(max_length=20, choices=ORIGEN_EGRESO, default="manual")
    confianza_ia = models.FloatField(null=True, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos_capturados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    anulado = models.BooleanField(default=False, db_index=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="egresos_anulados",
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    objects = models.Manager()
    vigentes = EgresoNoAnuladoManager()

    class Meta:
        db_table = "tesoreria_egreso"
        ordering = ["-fecha", "-creado_en"]
        indexes = [
            models.Index(fields=["-fecha"]),
            models.Index(fields=["proyecto", "-fecha"]),
            models.Index(fields=["centro_de_costo", "-fecha"]),
            models.Index(fields=["estado_pago"]),
            models.Index(fields=["pagado_por", "estado_pago"]),
        ]

    def __str__(self):
        return f"{self.codigo} · ${self.monto}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            from .ingreso import _generar_codigo
            anio = (self.fecha or date.today()).year
            with transaction.atomic():
                self.codigo = _generar_codigo("EGR", anio)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)
