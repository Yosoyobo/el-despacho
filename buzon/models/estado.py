"""Estado configurable del Buzón / tickets (espejo de EstadoProyecto).

S-Buzon-Estados-V1: los 4 estados base (sistema=True) se siembran en
migración. El super_admin puede editar label/color/orden, marcar terminal
o activo, y agregar estados nuevos (sistema=False, borrables). Vive en la
app shared `buzon/` para que tanto El Taller (consume) como La Gerencia
(CRUD) lo importen directo.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

# El color es un HEX libre (#RRGGBB) capturado desde la UI. El render usa
# color-mix sobre la custom property --ec, así que cualquier hex queda
# legible en claro y oscuro (idéntico a Estados de proyecto).
HEX_COLOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
)

# Slug → (label, color, orden, terminal). Sembrado como sistema=True en la
# migración 0004. Los colores espejan los KPI hero del Buzón
# (Nuevos=blue-light · Leídos=brand · Respondidos=success · Archivados=purple).
ESTADOS_BASE = (
    ("nuevo",      "Nuevo",      "#0ba5ec", 10, False),
    ("leido",      "Leído",      "#465fff", 20, False),
    ("respondido", "Respondido", "#12b76a", 30, False),
    ("archivado",  "Archivado",  "#7a5af8", 40, True),
)


class EstadoBuzon(models.Model):
    """Estado de un mensaje/ticket del Buzón, configurable desde La Gerencia."""

    slug = models.SlugField(max_length=32, unique=True, db_index=True)
    label = models.CharField(max_length=64)
    color = models.CharField(max_length=7, default="#667085", validators=[HEX_COLOR],
                             help_text="Color HEX del badge, ej. #465fff.")
    orden = models.PositiveSmallIntegerField(default=100)
    terminal = models.BooleanField(default=False, help_text="Si está marcado, el ticket se considera cerrado.")
    activo = models.BooleanField(default=True)
    sistema = models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buzon_estado"
        verbose_name = "estado del Buzón"
        verbose_name_plural = "estados del Buzón"
        ordering = ["orden", "label"]

    def __str__(self):
        return self.label
