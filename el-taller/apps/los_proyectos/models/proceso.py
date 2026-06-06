"""Procesos/gastos de un producto del proyecto (S-LC-Proyecto-Render-V1).

Cada línea de producto (`ProyectoProducto`) puede llevar:

- **Impresión** (`tipo="impresion"`): un proceso ligado a un PROVEEDOR. El
  monto se cuenta como gasto del proyecto y se le adeuda a ese proveedor
  (ver `Proyecto.deuda_por_proveedor`).
- **Operativos** (`tipo="operativo"`): gastos de compra de materiales extra
  SIN proveedor del catálogo (clavos, pegamento, viáticos, embalaje…). Se
  enlistan en los gastos del proyecto con su descripción.

Decisión de diseño (confirmada con LC):
- El costo de cada proceso es **fijo**: NO se multiplica por la cantidad del
  producto (a diferencia del costo unitario del producto principal, que sí).
- Los procesos suman al **Costo de producción** del proyecto (bajan la
  utilidad) pero NO tocan el "Monto calculado" (precio de venta) ni el
  "Monto a facturar".
- Solo cuentan si el producto padre está marcado `incluir_en_calculo`.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")


class ProyectoProductoProceso(models.Model):
    TIPO_IMPRESION = "impresion"
    TIPO_OPERATIVO = "operativo"
    TIPO_CHOICES = [
        (TIPO_IMPRESION, "Impresión"),
        (TIPO_OPERATIVO, "Gasto operativo"),
    ]

    producto = models.ForeignKey(
        "proyectos.ProyectoProducto",
        on_delete=models.CASCADE,
        related_name="procesos",
    )
    tipo = models.CharField(max_length=16, choices=TIPO_CHOICES, default=TIPO_OPERATIVO)
    orden = models.PositiveSmallIntegerField(default=0)
    # Solo para tipo=impresion: proveedor del catálogo al que se le adeuda.
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="procesos_proyecto",
    )
    # Solo para tipo=operativo: texto libre (Clavos, pegamento, viáticos…).
    descripcion = models.CharField(max_length=200, blank=True, default="")
    # Monto FIJO del proceso (no se multiplica por la cantidad del producto).
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto_proceso"
        ordering = ["orden", "creado_en"]
        verbose_name = "proceso del producto"
        verbose_name_plural = "procesos del producto"

    def __str__(self) -> str:
        if self.tipo == self.TIPO_IMPRESION and self.proveedor_id:
            return f"Impresión · {self.proveedor.razon_social} · {self.costo}"
        return f"{self.descripcion or 'Gasto'} · {self.costo}"

    @property
    def costo_decimal(self) -> Decimal:
        return Decimal(str(self.costo or 0))

    @property
    def etiqueta(self) -> str:
        """Nombre legible del proceso para listados de gastos."""
        if self.tipo == self.TIPO_IMPRESION:
            return f"Impresión — {self.proveedor.razon_social}" if self.proveedor_id else "Impresión"
        return self.descripcion or "Gasto operativo"
