"""Variaciones de un Servicio del Catálogo.

LC necesita modelar que un mismo producto (ej. "Playera promocional") tiene
muchas variantes según tela, tamaño, color, tintas, impresión. La variación
captura esas dimensiones para que costo, descripción y opción de impresión
sean específicos por variante sin duplicar el servicio padre.
"""

from __future__ import annotations

from django.db import models


class Variacion(models.Model):
    servicio = models.ForeignKey(
        "el_catalogo.Servicio", on_delete=models.CASCADE, related_name="variaciones"
    )
    nombre = models.CharField(
        max_length=150,
        help_text="Ej.: 'Talla M · algodón blanco · 1 tinta'.",
    )
    costo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Lo que cuesta fabricarlo o comprarlo, sin IVA.",
    )

    impresion_activa = models.BooleanField(
        default=False,
        help_text="Activar si esta variación lleva impresión.",
    )
    impresion_costo = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, blank=True,
    )
    impresion_descripcion = models.CharField(
        max_length=250, blank=True, default="",
        help_text="Detalles de la impresión (tintas, técnica, posición).",
    )

    descripcion = models.CharField(
        max_length=500, blank=True, default="",
        help_text="Detalles cortos: tela, tamaño, color, etc.",
    )
    disponible = models.BooleanField(default=True, db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogo_variacion"
        ordering = ["servicio__nombre", "nombre"]
        verbose_name = "variación"
        verbose_name_plural = "variaciones"

    def __str__(self) -> str:
        return f"{self.servicio.nombre} · {self.nombre}"

    @property
    def costo_total(self):
        """Costo + impresión (si está activa)."""
        total = self.costo or 0
        if self.impresion_activa:
            total += self.impresion_costo or 0
        return total
