"""Tipo de mensaje del Buzón, configurable desde La Gerencia (S-LC-Buzon-V2).

Espejo de EstadoBuzon: los tipos base (sugerencia/problema/otro) se siembran
como sistema=True; el super_admin puede renombrar/recolorear/reordenar y
agregar tipos nuevos (sistema=False, borrables si ningún ticket los usa). Vive
en la app shared `buzon/` para que El Taller (consume) y La Gerencia (CRUD) lo
importen directo. El slug `problema` se preserva siempre porque el Colador
(lib.colador) redacta el cuerpo de los mensajes de ese tipo.
"""

from __future__ import annotations

from django.db import models

from buzon.models.estado import HEX_COLOR

# Slug → (label, color, orden). Sembrados como sistema=True en la migración.
TIPOS_BASE = (
    ("sugerencia", "Sugerencia",     "#465fff", 10),
    ("problema",   "Problema / bug", "#f04438", 20),
    ("otro",       "Otro",           "#667085", 30),
)


class TipoBuzon(models.Model):
    """Tipo de un mensaje del Buzón, configurable desde La Gerencia."""

    slug = models.SlugField(max_length=32, unique=True, db_index=True)
    label = models.CharField(max_length=64)
    color = models.CharField(max_length=7, default="#667085", validators=[HEX_COLOR],
                             help_text="Color HEX del badge, ej. #465fff.")
    orden = models.PositiveSmallIntegerField(default=100)
    activo = models.BooleanField(default=True)
    sistema = models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buzon_tipo"
        verbose_name = "tipo del Buzón"
        verbose_name_plural = "tipos del Buzón"
        ordering = ["orden", "label"]

    def __str__(self):
        return self.label
