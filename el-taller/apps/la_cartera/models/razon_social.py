"""Razones sociales de facturación de un Cliente.

LC 2026-07-26 (Oscar): «un cliente puede facturar bajo diferentes razones
sociales, agreguemos esta habilidad de agregar más de la primera». Y al revés:
una misma razón social (p. ej. Grupo Lazanto) puede aplicar para DOS clientes
distintos (Cueva y Kari Kari) — por eso el RFC dejó de ser único en la cartera.

La `principal` es la que se espeja a los campos legacy `Cliente.razon_social_fiscal`
y `Cliente.rfc` (mismo patrón que `ClienteContacto` con los campos de contacto):
así la búsqueda, el CFDI y el código viejo siguen funcionando sin cambios.
"""

from __future__ import annotations

from django.db import models


class ClienteRazonSocial(models.Model):
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.CASCADE, related_name="razones_sociales",
    )
    razon_social = models.CharField(
        max_length=200,
        help_text="Nombre legal como aparece en el CFDI.",
    )
    rfc = models.CharField(max_length=13, blank=True, default="", db_index=True)
    principal = models.BooleanField(
        default=False,
        help_text="La que se usa por default al facturar.",
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cartera_cliente_razon_social"
        ordering = ["-principal", "razon_social"]
        verbose_name = "razón social de cliente"
        verbose_name_plural = "razones sociales de cliente"

    def __str__(self) -> str:
        return f"{self.razon_social}{f' ({self.rfc})' if self.rfc else ''}"
