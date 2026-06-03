"""Productos/servicios del catálogo involucrados en un proyecto.

Permite mostrar el "resumen compacto" debajo de cada proyecto en la lista
y armar el form de Nuevo Proyecto eligiendo desde el catálogo. Una línea
puede apuntar a Servicio (genérico) o Variacion (específica del producto).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")


class ProyectoProducto(models.Model):
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.CASCADE, related_name="productos"
    )
    servicio = models.ForeignKey(
        "el_catalogo.Servicio", on_delete=models.PROTECT, related_name="en_proyectos"
    )
    variacion = models.ForeignKey(
        "el_catalogo.Variacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="en_proyectos",
    )
    cantidad = models.PositiveIntegerField(default=1)
    # C4 S-LC-Feedback-V6: precio/costo por proyecto (override). Si quedan en
    # null, se heredan del catálogo (servicio.precio_base / costo de la
    # variación o servicio). `merma` = piezas extra que se fabrican para ESTE
    # proyecto: cuentan al costo pero NO se le cobran al cliente.
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Precio por unidad para este proyecto. Vacío = usa el del catálogo.",
    )
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Costo por unidad para este proyecto. Vacío = usa el del catálogo.",
    )
    merma = models.PositiveIntegerField(
        default=0,
        help_text="Piezas extra (muestras, control de calidad, regalos). Suman costo, no se cobran.",
    )
    # C7 S-LC-Feedback-V6: si está desmarcado, la línea NO entra en los
    # cálculos de dinero del proyecto (monto calculado / IVA / costo).
    incluir_en_calculo = models.BooleanField(default=True)
    nota = models.CharField(max_length=200, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto"
        ordering = ["creado_en"]
        verbose_name = "producto del proyecto"
        verbose_name_plural = "productos del proyecto"

    def __str__(self) -> str:
        if self.variacion_id:
            return f"{self.servicio.nombre} · {self.variacion.nombre} ×{self.cantidad}"
        return f"{self.servicio.nombre} ×{self.cantidad}"

    @property
    def etiqueta(self) -> str:
        """Etiqueta compacta para el resumen de lista de proyectos."""
        base = self.variacion.nombre if self.variacion_id else self.servicio.nombre
        if self.cantidad > 1:
            return f"{base} ×{self.cantidad}"
        return base

    # ── Precio / costo / merma (C4 S-LC-Feedback-V6) ──────────────────────────

    @property
    def precio_efectivo(self) -> Decimal:
        """Precio unitario: override del proyecto o, si no, el del catálogo."""
        if self.precio_unitario is not None:
            return Decimal(str(self.precio_unitario))
        base = self.servicio.precio_base if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def costo_efectivo(self) -> Decimal:
        """Costo unitario: override del proyecto o, si no, el del catálogo
        (costo de la variación si existe, si no el del servicio)."""
        if self.costo_unitario is not None:
            return Decimal(str(self.costo_unitario))
        if self.variacion_id:
            return Decimal(str(self.variacion.costo_total or 0))
        base = self.servicio.costo if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def subtotal(self) -> Decimal:
        """Lo que se le cobra al cliente por esta línea (precio × cantidad).
        La merma NO se cobra, por eso no entra aquí."""
        return self.precio_efectivo * self.cantidad

    @property
    def merma_costo(self) -> Decimal:
        """Costo de las piezas de merma (costo × merma)."""
        return self.costo_efectivo * self.merma

    @property
    def costo_total_linea(self) -> Decimal:
        """Costo real de producir la línea: incluye las piezas de merma."""
        return self.costo_efectivo * (self.cantidad + self.merma)

    @property
    def utilidad(self) -> Decimal:
        """Subtotal menos el costo real (incluyendo merma)."""
        return self.subtotal - self.costo_total_linea
