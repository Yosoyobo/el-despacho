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
    # S-Finanzas-UX (2026-07): 4 decimales para tasas fraccionadas (ej. la
    # retención de IVA de honorarios 10.6667%). max_digits=7 → hasta 999.9999.
    # El widget del ModelForm hereda step="0.0001" de decimal_places.
    porcentaje = models.DecimalField(max_digits=7, decimal_places=4)
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

    @property
    def porcentaje_str(self) -> str:
        """Porcentaje sin ceros de relleno: 16.0000 → "16", 10.6667 → "10.6667"."""
        s = f"{self.porcentaje:.4f}".rstrip("0").rstrip(".")
        return s or "0"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.porcentaje_str}%)"
