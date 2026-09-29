"""Cómo se comporta un KPI en todo el despacho (S-KPIs-V2, 2026-09-29).

Lo edita quien tiene `kpis.configurar` en La Gerencia → Ajustes → KPIs. Sin
fila, el KPI se comporta como lo declara su código (`kpis.KPI`): prendido, con
su dirección y sin umbrales.

- `activo=False` lo apaga para TODOS: no sale en tableros, ni en preferencias,
  ni en El Chalán. No borra su historia.
- `direccion` vacío = la del catálogo; lleno, la sustituye.
- Umbrales: vacío = sin umbral (regla «vacío no es cero»). Con dirección
  «sube», amarillo/rojo son pisos (por DEBAJO se pinta); con «baja», techos.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from ..kpi_meta import DIRECCIONES


class ConfigKPI(models.Model):
    kpi_slug = models.CharField(max_length=80, unique=True)
    activo = models.BooleanField(default=True)
    direccion = models.CharField(max_length=10, blank=True, default="", choices=DIRECCIONES)
    umbral_amarillo = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    umbral_rojo = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="config_kpi_modificadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "taller_home_config_kpi"
        ordering = ["kpi_slug"]

    def __str__(self) -> str:
        return f"{self.kpi_slug} ({'activo' if self.activo else 'apagado'})"
