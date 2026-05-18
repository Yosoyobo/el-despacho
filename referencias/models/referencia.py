"""Tabla `referencia` — registro polimórfico de menciones `@/#/$` en contenedores.

Cada fila representa UNA mención dentro de un contenedor (recado, dictado,
comentario, etc.). El contenedor se identifica con `(contenedor_tipo,
contenedor_id)` — sin FK genérica para evitar acoplamiento.

CHECK constraint asegura que exactamente uno de los 3 FKs esté poblado y que
matchee con el `tipo`.
"""

from __future__ import annotations

from django.db import models


TIPOS_REFERENCIA = (
    ("usuario", "Usuario"),
    ("proyecto", "Proyecto"),
    ("cliente", "Cliente"),
)


class Referencia(models.Model):
    contenedor_tipo = models.CharField(max_length=30, db_index=True)
    contenedor_id = models.BigIntegerField(db_index=True)

    tipo = models.CharField(max_length=10, choices=TIPOS_REFERENCIA, db_index=True)
    usuario = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referencias_recibidas",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referencias_recibidas",
    )
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referencias_recibidas",
    )

    token_original = models.CharField(max_length=200)
    posicion_inicio = models.IntegerField()
    posicion_fin = models.IntegerField()

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "referencias_referencia"
        indexes = [
            models.Index(fields=["contenedor_tipo", "contenedor_id"]),
            models.Index(fields=["tipo", "usuario"]),
            models.Index(fields=["tipo", "proyecto"]),
            models.Index(fields=["tipo", "cliente"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(tipo="usuario") & models.Q(usuario__isnull=False)
                        & models.Q(proyecto__isnull=True) & models.Q(cliente__isnull=True))
                    | (models.Q(tipo="proyecto") & models.Q(proyecto__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(cliente__isnull=True))
                    | (models.Q(tipo="cliente") & models.Q(cliente__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(proyecto__isnull=True))
                ),
                name="referencia_tipo_fk_unica",
            ),
        ]

    def __str__(self):
        return f"{self.contenedor_tipo}#{self.contenedor_id} → {self.token_original}"

    @property
    def entidad(self):
        """Devuelve la entidad referenciada según el tipo, o None si está rota."""
        if self.tipo == "usuario":
            return self.usuario
        if self.tipo == "proyecto":
            return self.proyecto
        if self.tipo == "cliente":
            return self.cliente
        return None
