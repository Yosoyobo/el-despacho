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

# Acciones automáticas que se disparan cuando un mensaje ENTRA a este estado
# por una acción explícita del admin (S-LC-Buzon-V2). El auto-avance
# nuevo→leído al abrir NO las dispara (es automático, sería ruidoso).
ACCION_CHOICES = (
    ("ninguna",          "Ninguna"),
    ("notificar_autor",  "Avisar al autor del mensaje (push)"),
    ("notificar_admins", "Avisar a los admins del Buzón (push)"),
)


class EstadoBuzon(models.Model):
    """Estado de un mensaje/ticket del Buzón, configurable desde La Gerencia."""

    slug = models.SlugField(max_length=32, unique=True, db_index=True)
    label = models.CharField(max_length=64)
    descripcion = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Qué significa este estado (visible como ayuda al equipo).",
    )
    color = models.CharField(max_length=7, default="#667085", validators=[HEX_COLOR],
                             help_text="Color HEX del badge, ej. #465fff.")
    accion = models.CharField(
        max_length=24, choices=ACCION_CHOICES, default="ninguna",
        help_text="Acción automática al mover un mensaje a este estado.",
    )
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
