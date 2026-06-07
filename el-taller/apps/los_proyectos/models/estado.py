from django.db import models

# Colores TailAdmin disponibles para badges de estado (alineados con
# templatetag `color_estado`). Mantén consistencia con la paleta del repo.
COLORES_ESTADO = (
    ("badge-blue", "Azul"),
    ("badge-orange", "Naranja"),
    ("badge-warning", "Amarillo"),
    ("badge-success", "Verde"),
    ("badge-error", "Rojo"),
    ("badge-gray", "Gris"),
    ("badge-brand", "Brand"),
)

# Slug → (label, color, orden, terminal). Sembrado como sistema=True en
# la migración 0007. Si LC quiere cambiar labels/colores, lo hace desde
# la UI de Gerencia sin tocar código.
ESTADOS_BASE = (
    ("por_cotizar",            "Por cotizar",            "badge-blue",     10, False),
    ("esperando_respuesta",    "Esperando respuesta",    "badge-orange",   20, False),
    ("en_proceso_diseno",      "En proceso de diseño",   "badge-warning",  30, False),
    ("en_proceso_produccion",  "En proceso de producción", "badge-warning", 40, False),
    ("entregado",              "Entregado",              "badge-success",  50, True),
    ("cerrado",                "Cerrado",                "badge-brand",    55, True),
    ("en_pausa",               "En pausa",               "badge-gray",     60, False),
    ("cancelado",              "Cancelado",              "badge-error",    70, True),
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
    color = models.CharField(max_length=24, choices=COLORES_ESTADO, default="badge-gray")
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
