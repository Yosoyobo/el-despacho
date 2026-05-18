"""CuadroChalanes — qué Chalán atiende cada estación a nivel de equipo.

Una fila por estación. El super_admin la edita desde `/chalanes/` (La Gerencia).
"""

from __future__ import annotations

from django.db import models

PROVEEDORES = (
    ("anthropic", "Chalán Claudio (Anthropic)"),
    ("openai", "Chalán GPT (OpenAI)"),
    ("deepseek", "Chalán Chino (Deepseek)"),
    ("gemini", "Chalán Gemini (Google)"),
)


class CuadroChalanes(models.Model):
    estacion = models.CharField(max_length=40, unique=True, db_index=True)
    proveedor = models.CharField(max_length=30, choices=PROVEEDORES)
    modelo = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=200, blank=True, default="")
    requiere_vision = models.BooleanField(default=False)
    actualizado_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cuadro_chalanes_actualizados",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chalanes_cuadro"
        ordering = ["estacion"]

    def __str__(self):
        return f"{self.estacion} → {self.proveedor} ({self.modelo})"
