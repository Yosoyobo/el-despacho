"""Cuánto de un gasto del proyecto cubre cada pago (Oscar 2026-10-14).

Un gasto (línea de producto o proceso) tiene UN `egreso` (FK), que dice «este gasto
ya se pagó». Eso no alcanza para los pagos parciales («anticipo 50% hoy, el resto el
mes que entra», o «sólo dos de los tres pedidos de la tienda»): el gasto no está ni
pagado ni sin pagar. Esta tabla guarda, por cada egreso que paga todo o parte de un
gasto, CUÁNTO le abona (en la misma base sin IVA con la que se mide el gasto).

Pendiente de un gasto = su costo − Σ de sus abonos cuyo egreso sigue vigente y ya se
pagó (`gastos.iter_unidades`). Anular el egreso de un abono devuelve ese monto a
«pendiente» solo, sin tocar nada más.
"""

from django.db import models


class PagoGasto(models.Model):
    egreso = models.ForeignKey(
        "tesoreria.Egreso", on_delete=models.CASCADE, related_name="pagos_gasto",
    )
    producto = models.ForeignKey(
        "proyectos.ProyectoProducto", null=True, blank=True,
        on_delete=models.CASCADE, related_name="pagos_gasto",
    )
    proceso = models.ForeignKey(
        "proyectos.ProyectoProductoProceso", null=True, blank=True,
        on_delete=models.CASCADE, related_name="pagos_gasto",
    )
    # Abono a ESE gasto, sin IVA (misma base que `gastos.iter_unidades()["monto"]`).
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_pago_gasto"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(producto__isnull=False, proceso__isnull=True)
                    | models.Q(producto__isnull=True, proceso__isnull=False)
                ),
                name="pago_gasto_un_solo_gasto",
            ),
        ]

    def __str__(self):
        return f"abono ${self.monto} · egreso {self.egreso_id}"
