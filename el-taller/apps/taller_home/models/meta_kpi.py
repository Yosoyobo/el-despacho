"""Metas de los KPIs (S-LC-Feedback-V5 c8; ámbitos y avisos en S-KPIs-V2).

Una meta se pone al despacho, a una persona o a un cliente:

- `despacho`: el número de todo el despacho («ingresos del mes ≥ 250 mil»).
- `persona`: el de alguien — un KPI personal («mis horas») o uno que se
  reparte por persona («vendido por persona»). Lleva `usuario`.
- `cliente`: el de un cliente, en un KPI que se reparte por cliente. Lleva
  `cliente`.

`periodo` se deriva del KPI (`acumula`): una meta sobre un número que vuelve a
cero cada mes se mide proporcional al avance del mes; la de un saldo, al corte.
`avisado_periodo` recuerda el último periodo en que se avisó «en riesgo»
(se avisa una sola vez por periodo).

La editan quienes tienen `kpis.configurar` desde La Gerencia → Ajustes → KPIs.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

PERIODOS = (
    ("dia", "Diario"),
    ("semana", "Semanal"),
    ("mes", "Mensual"),
    ("trimestre", "Trimestral"),
    ("ano", "Anual"),
    ("corte", "Al corte"),
)
AMBITOS = (
    ("despacho", "Todo el despacho"),
    ("persona", "Una persona"),
    ("cliente", "Un cliente"),
)


class MetaKPI(models.Model):
    kpi_slug = models.CharField(max_length=80, db_index=True)
    ambito = models.CharField(max_length=10, choices=AMBITOS, default="despacho")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="metas_kpi",
    )
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.CASCADE, null=True, blank=True,
        related_name="metas_kpi",
    )
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    periodo = models.CharField(max_length=20, choices=PERIODOS, default="mes")
    activa = models.BooleanField(default=True)
    avisado_periodo = models.CharField(max_length=20, blank=True, default="")
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="metas_kpi_modificadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "taller_home_meta_kpi"
        ordering = ["kpi_slug", "ambito", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["kpi_slug"], condition=models.Q(ambito="despacho"),
                name="uniq_meta_kpi_despacho",
            ),
            models.UniqueConstraint(
                fields=["kpi_slug", "usuario"], condition=models.Q(ambito="persona"),
                name="uniq_meta_kpi_persona",
            ),
            models.UniqueConstraint(
                fields=["kpi_slug", "cliente"], condition=models.Q(ambito="cliente"),
                name="uniq_meta_kpi_cliente",
            ),
        ]

    def __str__(self) -> str:
        quien = self.usuario or self.cliente or "despacho"
        return f"{self.kpi_slug} · {quien} = {self.valor} ({self.periodo})"
