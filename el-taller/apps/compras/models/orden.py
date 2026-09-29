"""OrdenCompra — lo que se le pide a un proveedor (2026-09-29).

Oscar pidió, en el arco de La Imprenta, poder mandarle al proveedor una orden de
compra en PDF: qué se le pide, cuánto, a qué precio acordado y para cuándo,
ligada al proyecto. Hasta hoy no existía: el pedido iba por WhatsApp y el
registro quedaba sólo en el egreso cuando se pagaba.

No mueve dinero: una orden no es un egreso (el egreso nace al pagar, como
siempre). Es el papel que dice qué se pidió.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

ESTADOS_ORDEN = (
    ("borrador", "Borrador"),
    ("enviada", "Enviada al proveedor"),
    ("recibida", "Recibida"),
    ("cancelada", "Cancelada"),
)


def _generar_codigo(anio: int) -> str:
    """OC-YYYY-NNNN con el correlativo del año (dentro de `atomic`)."""
    prefijo = f"OC-{anio}-"
    ultimo = (OrdenCompra.objects.select_for_update().filter(codigo__startswith=prefijo)
              .order_by("-codigo").first())
    n = 1
    if ultimo:
        try:
            n = int(ultimo.codigo.rsplit("-", 1)[-1]) + 1
        except ValueError:
            n = 1
    return f"{prefijo}{n:04d}"


class OrdenCompra(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    proveedor = models.ForeignKey("el_catalogo.Proveedor", on_delete=models.PROTECT,
                                  related_name="ordenes_compra")
    proyecto = models.ForeignKey("proyectos.Proyecto", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="ordenes_compra")
    estado = models.CharField(max_length=12, choices=ESTADOS_ORDEN, default="borrador",
                              db_index=True)
    fecha = models.DateField(default=date.today)
    fecha_entrega = models.DateField(null=True, blank=True,
                                     help_text="Para cuándo se necesita.")
    moneda = models.CharField(max_length=3, default="MXN")
    condiciones = models.TextField(blank=True, default="",
                                   help_text="Forma de pago, entrega, empaque…")
    notas = models.TextField(blank=True, default="")
    enviada_en = models.DateTimeField(null=True, blank=True)
    recibida_en = models.DateTimeField(null=True, blank=True)
    cancelada_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compras_orden"
        ordering = ["-fecha", "-pk"]
        verbose_name = "orden de compra"
        verbose_name_plural = "órdenes de compra"

    def __str__(self) -> str:
        return f"{self.codigo} · {self.proveedor}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            with transaction.atomic():
                self.codigo = _generar_codigo((self.fecha or date.today()).year)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @property
    def total(self) -> Decimal:
        return sum((it.subtotal for it in self.items.all()), Decimal("0.00"))

    @property
    def es_editable(self) -> bool:
        return self.estado in ("borrador", "enviada")


class OrdenCompraItem(models.Model):
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="items")
    orden = models.PositiveIntegerField(default=0)
    descripcion = models.CharField(max_length=300)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unidad = models.CharField(max_length=30, default="pz", blank=True)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "compras_orden_item"
        ordering = ["orden", "pk"]

    def __str__(self) -> str:
        return self.descripcion

    @property
    def subtotal(self) -> Decimal:
        return (Decimal(self.cantidad or 0) * Decimal(self.precio_unitario or 0)).quantize(Decimal("0.01"))
