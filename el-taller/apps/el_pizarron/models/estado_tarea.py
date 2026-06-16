"""EstadoTarea configurable (S-LC-Feedback-V6 Bloque 1).

Espejo del patrón S-Proyecto-Estados-V1 (`los_proyectos.models.estado`):
estados de tarea editables desde La Gerencia (label, color HEX, orden,
terminal, activo). Los sembrados con sistema=True no se borran.

"Atrasada" NO es un estado almacenado: es derivado (fecha de compromiso
vencida + estado no terminal) — ver `Tarea.esta_atrasada`.
"""

from apps.los_proyectos.models.estado import HEX_COLOR
from django.db import models

# Slug → (label, color, orden, terminal). Sembrado como sistema=True en la
# migración 0004. "bloqueada" se eliminó (migra a "pendiente"); "Atrasada"
# es derivada y no vive aquí.
ESTADOS_TAREA_BASE = (
    ("pendiente",  "Pendiente",  "#0ba5ec", 10, False),
    ("en_curso",   "En curso",   "#465fff", 20, False),
    ("completada", "Completada", "#12b76a", 30, True),
)

# Acción prevista al mover una tarea a este estado. Espejo del patrón del Buzón
# para que las tres pantallas de Gerencia luzcan igual. POR AHORA ES DOCUMENTAL
# (se muestra en la columna "Acción"); el push automático se cablea después.
ACCION_CHOICES = (
    ("ninguna",            "Ninguna"),
    ("notificar_asignado", "Avisar a la persona asignada (push)"),
    ("notificar_todos",    "Avisar a TODO el equipo (push)"),
)


class EstadoTarea(models.Model):
    """Estado de una Tarea del Pizarrón, configurable desde La Gerencia."""

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
        help_text="Acción prevista al mover una tarea a este estado "
                  "(documental por ahora; el push automático llega después).",
    )
    orden = models.PositiveSmallIntegerField(default=100)
    terminal = models.BooleanField(default=False, help_text="Si está marcado, la tarea se considera cerrada.")
    activo = models.BooleanField(default=True)
    sistema = models.BooleanField(default=False, help_text="Sembrado por código; no se puede borrar.")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pizarron_estado"
        verbose_name = "estado de tarea"
        verbose_name_plural = "estados de tarea"
        ordering = ["orden", "label"]

    def __str__(self):
        return self.label


# --- Cache de proceso (60s) — compartido por templatetags y el modelo Tarea ---

_CLAVE_CACHE = "pizarron:mapa_estados:v1"


def mapa_estados_tarea() -> dict:
    """Mapa slug → {label, color, terminal}. Cache 60s; tolerante a DB sin
    migrar (tests aislados, primer boot)."""
    from django.core.cache import cache
    cacheado = cache.get(_CLAVE_CACHE)
    if cacheado is not None:
        return cacheado
    try:
        mapa = {
            e.slug: {"label": e.label, "color": e.color, "terminal": e.terminal}
            for e in EstadoTarea.objects.all()
        }
        cache.set(_CLAVE_CACHE, mapa, 60)
        return mapa
    except Exception:
        return {}


def slugs_terminales_tarea() -> set:
    """Slugs de estados terminales (cerrados). Fallback si DB vacía."""
    mapa = mapa_estados_tarea()
    if mapa:
        return {slug for slug, d in mapa.items() if d.get("terminal")}
    return {"completada"}


def invalidar_mapa_estados_tarea():
    """Llamado desde signals al guardar/borrar EstadoTarea."""
    from django.core.cache import cache
    cache.delete(_CLAVE_CACHE)
