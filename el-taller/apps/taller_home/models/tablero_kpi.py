"""El tablero de KPIs de cada rol (S-KPIs-V2, 2026-09-29).

Decisión de Oscar: «Gerencia arma, cada quien ajusta». En La Gerencia se
decide qué KPIs ve cada rol en su Inicio y en qué orden; cada persona oculta o
agrega desde Perfil → Tablero (`PreferenciaKPI`), siempre dentro de lo que su
permiso le deja ver.

`rol=None` es el tablero POR OMISIÓN: el de quien no tiene ningún rol con
tablero propio. Nace con los 8 KPIs que el Inicio pintaba fijos hasta hoy.
"""

from __future__ import annotations

from django.db import models


class TableroKPI(models.Model):
    rol = models.ForeignKey(
        "cuentas.Rol", on_delete=models.CASCADE, null=True, blank=True,
        related_name="tablero_kpis",
    )
    kpi_slug = models.CharField(max_length=80)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "taller_home_tablero_kpi"
        ordering = ["rol_id", "orden", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["rol", "kpi_slug"], name="uniq_tablero_rol_kpi"),
            models.UniqueConstraint(
                fields=["kpi_slug"], condition=models.Q(rol__isnull=True),
                name="uniq_tablero_omision_kpi",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rol or 'por omisión'} · {self.orden} · {self.kpi_slug}"
