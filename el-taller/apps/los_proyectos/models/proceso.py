"""Procesos/gastos de un producto del proyecto (S-LC-Proyecto-Render-V1).

Cada línea de producto (`ProyectoProducto`) puede llevar:

- **Impresión** (`tipo="impresion"`): un proceso ligado a un PROVEEDOR. El
  monto se cuenta como gasto del proyecto y se le adeuda a ese proveedor
  (ver `Proyecto.deuda_por_proveedor`).
- **Operativos** (`tipo="operativo"`): gastos de compra de materiales extra
  SIN proveedor del catálogo (clavos, pegamento, viáticos, embalaje…). Se
  enlistan en los gastos del proyecto con su descripción.

Decisión de diseño (S-LC-Proyecto-V2, Oscar 2026-06-16):
- Cada proceso elige si su costo es **fijo** (una vez por el proyecto, p.ej.
  viáticos, renta de equipo) o **por pieza** (`por_pieza=True`, se multiplica
  por las piezas producidas = cantidad + merma, p.ej. impresión por playera).
  Default: impresión nace "por pieza"; operativo nace "fijo".
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
    # Monto unitario del proceso. Si `por_pieza` es False, es el costo total
    # (fijo) del proceso; si es True, es el costo POR PIEZA y se multiplica por
    # las piezas producidas (cantidad + merma del producto padre).
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # S-LC-Proyecto-V2 (Oscar): impresión suele ser por pieza; viáticos/renta
    # suelen ser fijos. El default lo pone el form/data-migration por tipo.
    por_pieza = models.BooleanField(default=False)

    # Egreso de Tesorería que registra ESTE gasto (contabilidad en línea).
    # Cada gasto se liga por separado (decisión Oscar 2026-06-12). Marca de
    # idempotencia: un proceso con egreso no vuelve a generar. SET_NULL: si el
    # egreso se borra, el proceso queda "no registrado" y se puede re-registrar.
    egreso = models.ForeignKey(
        "tesoreria.Egreso",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="procesos_proyecto",
    )

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
    def piezas_producidas(self) -> int:
        """Piezas a producir del producto padre (cantidad + merma)."""
        prod = self.producto
        return (prod.cantidad or 0) + (prod.merma or 0)

    @property
    def costo_total(self) -> Decimal:
        """Costo total del proceso: fijo, o × piezas producidas si `por_pieza`."""
        c = self.costo_decimal
        return (c * self.piezas_producidas) if self.por_pieza else c

    @property
    def etiqueta(self) -> str:
        """Nombre legible del proceso para listados de gastos."""
        if self.tipo == self.TIPO_IMPRESION:
            base = f"Impresión — {self.proveedor.razon_social}" if self.proveedor_id else "Impresión"
        else:
            base = self.descripcion or "Gasto operativo"
        return base
