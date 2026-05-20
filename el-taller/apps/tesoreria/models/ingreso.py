from datetime import date

from django.conf import settings
from django.db import models, transaction

METODOS_INGRESO = (
    ("transferencia", "Transferencia"),
    ("deposito", "Depósito"),
    ("efectivo", "Efectivo"),
    ("cheque", "Cheque"),
    ("stripe", "Stripe"),
    ("mercadopago", "MercadoPago"),
    ("otro", "Otro"),
)


def _generar_codigo(prefijo: str, anio: int) -> str:
    """Genera ING-YYYY-NNNN / EGR-YYYY-NNNN tomando el max correlativo del año.
    Llamado dentro de transaction.atomic con select_for_update en la tabla."""
    from .egreso import Egreso

    modelo = Ingreso if prefijo == "ING" else Egreso
    prefijo_buscar = f"{prefijo}-{anio}-"
    ultimo = (
        modelo.objects.select_for_update()
        .filter(codigo__startswith=prefijo_buscar)
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
    return f"{prefijo_buscar}{n:04d}"


class IngresoNoAnuladoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(anulado=False)


class Ingreso(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=3, default="MXN")
    fecha = models.DateField()

    descripcion = models.CharField(max_length=300)

    cliente = models.ForeignKey(
        "cartera.Cliente", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ingresos",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ingresos",
    )

    metodo = models.CharField(max_length=30, choices=METODOS_INGRESO, default="transferencia")
    referencia_externa = models.CharField(max_length=100, blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ingresos_capturados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    anulado = models.BooleanField(default=False, db_index=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ingresos_anulados",
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    objects = models.Manager()
    vigentes = IngresoNoAnuladoManager()

    class Meta:
        db_table = "tesoreria_ingreso"
        ordering = ["-fecha", "-creado_en"]
        indexes = [
            models.Index(fields=["-fecha"]),
            models.Index(fields=["cliente", "-fecha"]),
            models.Index(fields=["proyecto", "-fecha"]),
        ]

    def __str__(self):
        return f"{self.codigo} · ${self.monto}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            anio = (self.fecha or date.today()).year
            with transaction.atomic():
                self.codigo = _generar_codigo("ING", anio)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)
