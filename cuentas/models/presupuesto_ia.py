"""PresupuestoIA — tope de gasto de IA en USD por usuario (S-Directorio-Panel-V1).

El Despacho no es SaaS (sin cobro), pero el super_admin puede acotar cuánto
gasta cada usuario en llamadas a Los Chalanes. Equivalente interno a las
"fichas" de La Cocina, pero medido en USD reales (desde `AnalistaLog`).

- `tope_usd = 0` → sin tope (la fila puede existir solo para configurar política).
- `politica`:
    - `alertar` (default) → al rebasar el tope solo se avisa (push + evento),
      la IA sigue funcionando.
    - `topar`    → al rebasar, las llamadas IA del usuario se rechazan hasta
      el siguiente mes (gate en `lib.analistas.analizar`).
- `alerta_mes` ("YYYY-MM") deduplica la alerta: el cron solo avisa una vez por
  mes por usuario.

Ausencia de fila = usuario sin tope ni política (comportamiento histórico).
"""

from __future__ import annotations

from django.db import models


class PresupuestoIA(models.Model):
    POLITICA_ALERTAR = "alertar"
    POLITICA_TOPAR = "topar"
    POLITICAS = [
        (POLITICA_ALERTAR, "Solo alertar"),
        (POLITICA_TOPAR, "Topar consumo"),
    ]

    usuario = models.OneToOneField(
        "cuentas.Usuario", on_delete=models.CASCADE, related_name="presupuesto_ia"
    )
    tope_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    politica = models.CharField(max_length=10, choices=POLITICAS, default=POLITICA_ALERTAR)
    activo = models.BooleanField(default=True)
    # "YYYY-MM" del último mes en que se emitió la alerta de rebase.
    alerta_mes = models.CharField(max_length=7, blank=True, default="")

    actualizado_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="presupuestos_ia_editados",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cuentas_presupuesto_ia"
        verbose_name = "presupuesto de IA"
        verbose_name_plural = "presupuestos de IA"

    def __str__(self) -> str:
        return f"{self.usuario_id} · ${self.tope_usd} ({self.politica})"
