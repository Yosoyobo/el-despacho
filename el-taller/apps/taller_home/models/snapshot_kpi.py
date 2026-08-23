"""La memoria de los indicadores: una foto diaria de cada KPI.

Sin esto el sistema sólo sabe decir cuánto vale algo HOY. Con esto puede decir
lo que de verdad importa: si subió o bajó, cuánto contra el mes pasado, y si el
valor de hoy se salió de lo normal.

Es la pieza que convierte un tablero en análisis. Todo lo demás de este módulo
—tendencias, comparación de periodos, detección de anomalías, metas propuestas
a partir del histórico— se apoya aquí.

Una fila por indicador y día. Con ~40 indicadores son unas 1,200 filas al mes:
nada para la base, y a cambio se puede mirar un año hacia atrás.
"""

from __future__ import annotations

from django.db import models


class SnapshotKPI(models.Model):
    kpi_slug = models.CharField(max_length=80, db_index=True)
    fecha = models.DateField(db_index=True)
    valor = models.DecimalField(
        max_digits=16, decimal_places=4,
        help_text="El número del indicador ese día.",
    )
    # Lo que acompañaba al número (la nota, el estado). Sirve para reconstruir
    # el contexto sin recalcular, y para que el Chalán lo lea al analizar.
    nota = models.CharField(max_length=200, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "taller_home_snapshot_kpi"
        verbose_name = "foto diaria de indicador"
        verbose_name_plural = "fotos diarias de indicadores"
        ordering = ["-fecha", "kpi_slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["kpi_slug", "fecha"], name="uniq_snapshot_kpi_dia",
            ),
        ]
        indexes = [models.Index(fields=["kpi_slug", "-fecha"])]

    def __str__(self) -> str:
        return f"{self.kpi_slug} · {self.fecha}: {self.valor}"
