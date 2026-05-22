"""Productos/servicios del catálogo involucrados en un proyecto.

Permite mostrar el "resumen compacto" debajo de cada proyecto en la lista
y armar el form de Nuevo Proyecto eligiendo desde el catálogo. Una línea
puede apuntar a Servicio (genérico) o Variacion (específica del producto).
"""

from __future__ import annotations

from django.db import models


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
