"""PermisoUsuario — permiso granular (módulo, acción) por usuario.

Migración seedea filas con defaults por rol; un super_admin las toggle desde
`/directorio/<id>/permisos/`. La función `lib.permisos.puede()` consulta esta
tabla.
"""

from __future__ import annotations

from django.db import models


class PermisoUsuario(models.Model):
    usuario = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.CASCADE, related_name="permisos_granulares"
    )
    modulo = models.CharField(max_length=40, db_index=True)
    permiso = models.CharField(max_length=60, db_index=True)
    activo = models.BooleanField(default=True)
    modificado_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="permisos_modificados",
    )
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cuentas_permiso_usuario"
        ordering = ["usuario_id", "modulo", "permiso"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "modulo", "permiso"], name="permiso_usuario_unico"
            ),
        ]

    def __str__(self):
        return f"{self.usuario_id}·{self.modulo}.{self.permiso}{'✓' if self.activo else '✗'}"
