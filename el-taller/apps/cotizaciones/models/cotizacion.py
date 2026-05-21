from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

ESTADOS_COTIZACION = (
    ("borrador", "Borrador"),
    ("enviada", "Enviada"),
    ("aprobada", "Aprobada"),
    ("rechazada", "Rechazada"),
    ("anulada", "Anulada"),
)

ESTADOS_TERMINAL = {"aprobada", "rechazada", "anulada"}

CERO = Decimal("0.00")


def _generar_codigo(anio: int) -> str:
    """COT-YYYY-NNNN tomando el max correlativo del año. Usar dentro de atomic."""
    prefijo = f"COT-{anio}-"
    ultimo = (
        Cotizacion.objects.select_for_update()
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


def _validez_default() -> date:
    return date.today() + timedelta(days=30)


class CotizacionVigentesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(estado="anulada")


class Cotizacion(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)

    cliente = models.ForeignKey(
        "cartera.Cliente",
        on_delete=models.PROTECT,
        related_name="cotizaciones",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones",
    )

    titulo = models.CharField(max_length=200)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_COTIZACION,
        default="borrador",
        db_index=True,
    )

    fecha_emision = models.DateField(default=date.today)
    fecha_validez = models.DateField(default=_validez_default)

    moneda = models.CharField(max_length=3, default="MXN")
    descuento_global_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    # Anticipo (S-Finanzas-V2 #E). Cuando la cotización está aprobada y
    # `anticipo_porcentaje > 0`, el monto se cuenta como "por cobrar"
    # hasta que se genere la factura del anticipo (vía service).
    # `anticipo_monto_override` permite fijar un monto absoluto distinto
    # al calculado del porcentaje (caso uso: redondeo a $5,000 exactos).
    anticipo_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="% del total que se cobra como anticipo. 0 = sin anticipo.",
    )
    anticipo_monto_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Monto absoluto del anticipo. Si se deja vacío, se calcula del porcentaje.",
    )
    anticipo_facturado_en = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuando se generó la factura del anticipo desde esta cotización.",
    )

    notas = models.TextField(blank=True, default="")
    terminos = models.TextField(blank=True, default="")

    # Envío
    enviada_en = models.DateTimeField(null=True, blank=True)
    enviada_a_email = models.CharField(max_length=200, blank=True, default="")

    # Aprobación / rechazo (lado cliente — texto libre)
    aprobada_en = models.DateTimeField(null=True, blank=True)
    aprobada_por_nombre = models.CharField(max_length=200, blank=True, default="")
    aprobada_por_email = models.CharField(max_length=200, blank=True, default="")
    referencia_aprobacion = models.CharField(max_length=200, blank=True, default="")

    rechazada_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, default="")

    # Anulación interna
    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_anuladas",
    )
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    vigentes = CotizacionVigentesManager()

    class Meta:
        db_table = "cotizaciones_cotizacion"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["cliente", "-creado_en"]),
            models.Index(fields=["proyecto", "-creado_en"]),
            models.Index(fields=["estado", "-fecha_emision"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            anio = (self.fecha_emision or date.today()).year
            with transaction.atomic():
                self.codigo = _generar_codigo(anio)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    # --- estado / propiedades derivadas ----------------------------------

    @property
    def es_editable(self) -> bool:
        return self.estado == "borrador"

    @property
    def es_terminal(self) -> bool:
        return self.estado in ESTADOS_TERMINAL

    @property
    def esta_vencida(self) -> bool:
        """Vencida = enviada sin respuesta y fecha_validez < hoy."""
        return self.estado == "enviada" and self.fecha_validez < date.today()

    @property
    def estado_visible(self) -> str:
        """Estado para UI: convierte 'enviada' en 'vencida' si aplica."""
        if self.esta_vencida:
            return "vencida"
        return self.estado

    # --- Anticipo (S-Finanzas-V2 #E) -------------------------------------

    @property
    def anticipo_monto(self) -> Decimal:
        """Monto del anticipo. Usa override si está, si no calcula del %."""
        if self.anticipo_monto_override is not None and self.anticipo_monto_override > 0:
            return Decimal(self.anticipo_monto_override).quantize(Decimal("0.01"))
        pct = self.anticipo_porcentaje or Decimal("0")
        if pct <= 0:
            return Decimal("0.00")
        total = self.calcular_totales()["total"]
        return (Decimal(total) * pct / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def anticipo_pendiente(self) -> bool:
        """True si el anticipo está configurado, cotización aprobada y
        aún no se ha generado la factura del anticipo."""
        return (
            self.estado == "aprobada"
            and self.anticipo_monto > 0
            and self.anticipo_facturado_en is None
        )

    # --- totales (calculados sobre items) --------------------------------

    def calcular_totales(self) -> dict:

        items = list(self.items.all())
        subtotal_items = sum((it.subtotal for it in items), CERO)

        desc_pct = self.descuento_global_porcentaje or CERO
        descuento_global = (subtotal_items * desc_pct / Decimal("100")).quantize(Decimal("0.01"))
        base_impuestos = (subtotal_items - descuento_global).quantize(Decimal("0.01"))

        trasladados = CERO
        retenciones = CERO
        impuestos_detalle = []
        for ci in self.impuestos.select_related("tasa").all():
            tasa = ci.tasa
            monto = (base_impuestos * tasa.porcentaje / Decimal("100")).quantize(Decimal("0.01"))
            if tasa.tipo == "retencion":
                retenciones += monto
            else:
                trasladados += monto
            impuestos_detalle.append({
                "id": ci.id,
                "tasa_id": tasa.id,
                "nombre": tasa.nombre,
                "tipo": tasa.tipo,
                "porcentaje": tasa.porcentaje,
                "monto": monto,
            })

        total = (base_impuestos + trasladados - retenciones).quantize(Decimal("0.01"))

        return {
            "subtotal_items": subtotal_items.quantize(Decimal("0.01")),
            "descuento_global": descuento_global,
            "base_impuestos": base_impuestos,
            "trasladados": trasladados.quantize(Decimal("0.01")),
            "retenciones": retenciones.quantize(Decimal("0.01")),
            "total": total,
            "impuestos_detalle": impuestos_detalle,
        }


class CotizacionItem(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="items"
    )
    orden = models.PositiveIntegerField(default=0, db_index=True)

    servicio = models.ForeignKey(
        "el_catalogo.Servicio",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="lineas_cotizacion",
    )
    descripcion = models.TextField()

    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unidad = models.CharField(max_length=30, default="pieza")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "cotizaciones_item"
        ordering = ["cotizacion", "orden", "pk"]

    def __str__(self) -> str:
        return f"{self.cotizacion.codigo} · {self.descripcion[:40]}"

    @property
    def subtotal(self) -> Decimal:
        bruto = (self.cantidad or CERO) * (self.precio_unitario or CERO)
        desc = (self.descuento_porcentaje or CERO) / Decimal("100")
        return (bruto * (Decimal("1") - desc)).quantize(Decimal("0.01"))


class CotizacionImpuesto(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="impuestos"
    )
    tasa = models.ForeignKey(
        "ajustes.TasaImpositiva", on_delete=models.PROTECT, related_name="cotizaciones"
    )
    aplicado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cotizaciones_impuesto"
        unique_together = (("cotizacion", "tasa"),)
        ordering = ["tasa__orden", "tasa__nombre"]

    def __str__(self) -> str:
        return f"{self.cotizacion.codigo} · {self.tasa.nombre}"
