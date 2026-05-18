"""ChalanAsignado — override personal por usuario × estación.

Si existe una fila `(usuario, estacion)`, sobreescribe al CuadroChalanes para
ese usuario. UI: `/perfil/chalanes/` en El Taller.
"""

from __future__ import annotations

from django.db import models


class ChalanAsignado(models.Model):
    usuario = models.ForeignKey("cuentas.Usuario", on_delete=models.CASCADE, related_name="chalanes_asignados")
    estacion = models.CharField(max_length=40, db_index=True)
    proveedor = models.CharField(max_length=30)
    modelo = models.CharField(max_length=80, blank=True, default="")
    motivo = models.CharField(max_length=200, blank=True, default="")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chalanes_asignado"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "estacion"], name="chalan_asignado_unico"),
        ]
        ordering = ["usuario_id", "estacion"]

    def __str__(self):
        return f"{self.usuario.email} · {self.estacion} → {self.proveedor}"
