"""Tabla `referencia` — registro polimórfico de menciones `@/#/$` en contenedores.

Cada fila representa UNA mención dentro de un contenedor (recado, dictado,
comentario, etc.). El contenedor se identifica con `(contenedor_tipo,
contenedor_id)` — sin FK genérica para evitar acoplamiento.

`usuario` es FK formal a `cuentas.Usuario` (app shared, disponible en los 3
Django projects). `proyecto_id` y `cliente_id` son **BigIntegerField sin FK**
porque `proyectos`/`cartera` viven en El Taller y NO están en INSTALLED_APPS
de La Gerencia — una app shared en raíz no puede tener FK a apps específicas
sin violar la dirección de dependencias (sería import cíclico conceptual).
El resolver hace lookup por slug en runtime; el modelo soft-deleta, no hay
borrado físico que requiera CASCADE.

CHECK constraint asegura que exactamente uno de los 3 campos esté poblado y
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
    proyecto_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    cliente_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    token_original = models.CharField(max_length=200)
    posicion_inicio = models.IntegerField()
    posicion_fin = models.IntegerField()

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "referencias_referencia"
        indexes = [
            models.Index(fields=["contenedor_tipo", "contenedor_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(tipo="usuario") & models.Q(usuario__isnull=False)
                        & models.Q(proyecto_id__isnull=True) & models.Q(cliente_id__isnull=True))
                    | (models.Q(tipo="proyecto") & models.Q(proyecto_id__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(cliente_id__isnull=True))
                    | (models.Q(tipo="cliente") & models.Q(cliente_id__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(proyecto_id__isnull=True))
                ),
                name="referencia_tipo_fk_unica",
            ),
        ]

    def __str__(self):
        return f"{self.contenedor_tipo}#{self.contenedor_id} → {self.token_original}"

    @property
    def entidad(self):
        """Lookup en runtime. Retorna None si está rota."""
        if self.tipo == "usuario":
            return self.usuario
        if self.tipo == "proyecto":
            if self.proyecto_id is None:
                return None
            try:
                from apps.los_proyectos.models.proyecto import Proyecto
                return Proyecto.objects.filter(pk=self.proyecto_id).first()
            except Exception:
                return None
        if self.tipo == "cliente":
            if self.cliente_id is None:
                return None
            try:
                from apps.la_cartera.models.cliente import Cliente
                return Cliente.objects.filter(pk=self.cliente_id).first()
            except Exception:
                return None
        return None
