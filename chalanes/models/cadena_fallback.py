"""CadenaFallback — orden global de reemplazo cuando el Chalán primario falla.

Cuando un Chalán lanza ErrorTransitorio (red/rate-limit/5xx) o FaltaCredencial,
El Reemplazo recorre `CadenaFallback` ordenada por `prioridad` ASC, saltando:
- el Chalán que ya falló
- Chalanes con `activo=False`
- Chalanes sin API key configurada
- Chalanes que no soportan la capability requerida (ej. visión)
"""

from __future__ import annotations

from django.db import models


class CadenaFallback(models.Model):
    proveedor = models.CharField(max_length=30, unique=True)
    prioridad = models.IntegerField(default=100, db_index=True)
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chalanes_cadena_fallback"
        ordering = ["prioridad"]

    def __str__(self):
        estado = "✓" if self.activo else "✗"
        return f"{self.prioridad}. {self.proveedor} {estado}"
