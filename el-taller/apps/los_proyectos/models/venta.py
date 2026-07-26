"""Procesos de VENTA de un producto del proyecto (LC 2026-07-26, Oscar).

Distintos de `ProyectoProductoProceso`, que son de PRODUCCIÓN (cuestan dinero y
bajan la utilidad). Éstos se le **cobran al cliente**: son el «subproceso» o
«subproducto» que acompaña al producto y se factura por separado.

    Producto: Bordado                    → lo que se le cobra por el bordado
      └ proceso de venta: Ponchado       → se le cobra aparte, como su propia
                                           línea de la cotización

En la cotización cada proceso de venta es una línea propia (con su cantidad y su
precio), pero se imprime DENTRO de la tabla de montos de su producto, para que el
cliente lea el bloque completo de un tirón (ver `CotizacionItem.agrupado`).

No tienen costo: si el proceso además cuesta producirlo, ese costo se captura
como proceso de producción (impresión / gasto operativo) en la misma tarjeta.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")


class ProyectoProductoVenta(models.Model):
    producto = models.ForeignKey(
        "proyectos.ProyectoProducto",
        on_delete=models.CASCADE,
        related_name="ventas",
    )
    orden = models.PositiveSmallIntegerField(default=0)
    descripcion = models.CharField(
        max_length=200,
        help_text="Cómo se le cobra al cliente (ej. «Ponchado», «Diseño de arte»).",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto_venta"
        ordering = ["orden", "creado_en"]
        verbose_name = "proceso de venta del producto"
        verbose_name_plural = "procesos de venta del producto"

    def __str__(self) -> str:
        return f"{self.descripcion} ×{self.cantidad}"

    @property
    def precio_decimal(self) -> Decimal:
        return Decimal(str(self.precio_unitario or 0))

    @property
    def subtotal(self) -> Decimal:
        """Lo que se le cobra al cliente por este proceso."""
        return (self.precio_decimal * (self.cantidad or 0)).quantize(Decimal("0.01"))

    @property
    def etiqueta(self) -> str:
        return self.descripcion or "Proceso"
