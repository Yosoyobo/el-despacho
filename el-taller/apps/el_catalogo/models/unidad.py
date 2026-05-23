"""Modelo Unidad — unidades de medida para CotizacionItem y FacturaItem.

Decisión S-LC-Feedback-V2: hasta ahora `unidad` era CharField libre.
Ahora hay un catálogo con CRUD. El campo CharField se mantiene en
CotizacionItem/FacturaItem por back-compat — los selects del form se
poblarán con el catálogo, pero la persistencia sigue siendo el string
(la conversión a FK queda como deuda diseñada para no romper migraciones).
"""

from __future__ import annotations

from django.db import models


class Unidad(models.Model):
    nombre = models.CharField(max_length=30, unique=True)
    abreviacion = models.CharField(max_length=10, blank=True, default="")
    orden = models.PositiveSmallIntegerField(default=10, db_index=True)
    activa = models.BooleanField(default=True, db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalogo_unidad"
        ordering = ["orden", "nombre"]
        verbose_name = "unidad de medida"
        verbose_name_plural = "unidades de medida"

    def __str__(self) -> str:
        return self.nombre
