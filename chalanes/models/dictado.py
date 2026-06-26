"""Vistas compartidas de `el_dictado_dictado` y `el_dictado_accion`.

El esquema lo mantiene `apps.el_dictado.models` (Taller). Estos modelos son
`managed = False` y apuntan al MISMO `db_table`, para que La Gerencia (que NO
instala `apps.el_dictado`) pueda leer el historial de Dictados al destilar
aprendizajes desde su botón de "barrido". Mismo patrón que
`chalanes.models.Aprendizaje` y `chalanes.models.ConocimientoNegocio`.

Solo se declaran los campos que el destilador necesita leer — no es un espejo
completo del modelo de Taller.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Dictado(models.Model):
    """Vista de solo-lectura del Dictado para el destilador de aprendizajes."""

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="+", db_column="autor_id",
    )
    texto_crudo = models.TextField()
    estado = models.CharField(max_length=30, default="interpretando")
    interpretacion_raw = models.JSONField(default=dict, blank=True)
    historial_clarificaciones = models.JSONField(default=list, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "chalanes"
        db_table = "el_dictado_dictado"
        managed = False
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"dictado#{self.pk} '{(self.texto_crudo or '')[:40]}'"


class DictadoAccion(models.Model):
    """Vista de solo-lectura de las acciones propuestas de un Dictado.

    `dictado_id` es un entero plano (no FK) — basta para filtrar por dictado
    y detectar acciones DESMARCADAS (`confirmada=False`) sin navegar el grafo
    cross-app.
    """

    dictado_id = models.BigIntegerField(db_column="dictado_id")
    tipo = models.CharField(max_length=40)
    descripcion = models.CharField(max_length=300)
    confirmada = models.BooleanField(default=True)

    class Meta:
        app_label = "chalanes"
        db_table = "el_dictado_accion"
        managed = False

    def __str__(self) -> str:
        return f"accion#{self.pk} {self.tipo}"
