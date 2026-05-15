"""Tasas impositivas configurables (IVA trasladado y retenciones).

Las cotizaciones y facturas (S2b) consultarán este modelo para armar el bloque
de impuestos. Las marcadas con `aplicable_default=True` se pre-seleccionan al
crear una cotización nueva.
"""

from __future__ import annotations

from django.db import models

TIPO_CHOICES = (
    ("trasladado", "Trasladado"),
    ("retencion", "Retención"),
)


class TasaImpositiva(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    aplicable_default = models.BooleanField(default=False)
    activa = models.BooleanField(default=True, db_index=True)
    orden = models.IntegerField(default=100, db_index=True)

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_tasa_impositiva"
        ordering = ["orden", "nombre"]
        verbose_name = "tasa impositiva"
        verbose_name_plural = "tasas impositivas"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.porcentaje}%)"
