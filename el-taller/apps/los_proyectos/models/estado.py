from django.core.validators import RegexValidator
from django.db import models

# S-Estados-Color-HEX: el color es ahora un HEX libre (#RRGGBB) que el
# super_admin captura desde la UI. Validador compartido por estados y
# categorías. El render usa color-mix sobre la custom property --ec, así
# que cualquier hex queda legible en claro y oscuro.
HEX_COLOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
)

# Sugerencias rápidas (chips del popover). Paleta canónica TailAdmin Pro 2.3.
COLORES_SUGERIDOS = (
    "#465fff", "#0ba5ec", "#12b76a", "#f79009",
    "#fb6514", "#f04438", "#7a5af8", "#667085",
)

# Slug → (label, color, orden, terminal). Sembrado como sistema=True en
# la migración 0007. Si LC quiere cambiar labels/colores, lo hace desde
# la UI de Gerencia sin tocar código.
ESTADOS_BASE = (
    ("por_cotizar",            "Por cotizar",            "#0ba5ec", 10, False),
    ("esperando_respuesta",    "Esperando respuesta",    "#fb6514", 20, False),
    ("en_proceso_diseno",      "En proceso de diseño",   "#f79009", 30, False),
    ("en_proceso_produccion",  "En proceso de producción", "#f79009", 40, False),
    ("entregado",              "Entregado",              "#12b76a", 50, True),
    ("cerrado",                "Cerrado",                "#465fff", 55, True),
    ("en_pausa",               "En pausa",               "#667085", 60, False),
    ("cancelado",              "Cancelado",              "#f04438", 70, True),
)

# Acción prevista al mover un proyecto a este estado. Espejo del patrón del
# Buzón (S-LC-Feedback-V6) para que las tres pantallas de Gerencia luzcan
# igual. POR AHORA ES DOCUMENTAL — describe la intención y se muestra en la
# columna "Acción"; el push automático al cambiar de estado se cablea después
# (decisión Oscar: "solo descriptivas por ahora").
ACCION_CHOICES = (
    ("ninguna",            "Ninguna"),
    ("notificar_equipo",   "Avisar al equipo del proyecto (push)"),
    ("notificar_lider",    "Avisar al líder / responsable (push)"),
    ("notificar_todos",    "Avisar a TODO el equipo (push)"),
)


class EstadoProyecto(models.Model):
    """Estado del ciclo de un Proyecto, configurable desde La Gerencia.

    S-Proyecto-Estados-V1: los 7 estados base (sistema=True) se siembran en
    migración. El super_admin puede editar label/color/orden, marcar
    terminal o activo, y agregar estados nuevos con sistema=False
    (borrables). Los sistema=True NO se pueden borrar para no romper
    proyectos existentes.
    """

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
        help_text="Acción prevista al mover un proyecto a este estado "
                  "(documental por ahora; el push automático llega después).",
    )
    orden = models.PositiveSmallIntegerField(default=100)
    terminal = models.BooleanField(default=False, help_text="Si está marcado, el proyecto se considera cerrado.")
    activo = models.BooleanField(default=True)
    sistema = models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "proyectos_estado"
        verbose_name = "estado de proyecto"
        verbose_name_plural = "estados de proyecto"
        ordering = ["orden", "label"]

    def __str__(self):
        return self.label
