"""Estados de cotización configurables desde La Gerencia.

Espejo del patrón de `EstadoProyecto` / `EstadoTarea`: el super_admin agrega
los pasos necesarios (Generada → Enviada → Aprobada → Pagada por default),
los renombra, reordena y colorea. El recuadro «Cotizaciones» del detalle de
proyecto pinta un pizza-tracker con estos pasos (crece/encoge según cuántos
haya) y el dropdown del estatus ofrece los activos.

El color es HEX libre (#RRGGBB) — se inyecta en la custom property `--ec` y
queda legible en claro/oscuro vía `color-mix` (mismo sistema que los estados
de proyecto, S-Estados-Color-HEX).
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
)

# ── Fase: qué SIGNIFICA cada paso para el negocio ─────────────────────────
#
# El nombre de un estado lo pone el despacho y puede ser cualquiera ("Generada",
# "En revisión del cliente", "Rechazada"…). Para medir conversión y detectar lo
# que se perdió, el sistema necesita saber qué significa cada paso, y eso NO se
# puede adivinar del nombre. Por eso cada estado declara su fase, editable en
# Gerencia junto con el resto.
#
# Antes de esto, los conteos buscaban los slugs literales 'borrador'/'enviada'.
# Learning Center apagó "Enviada" y usa "Generada", así que los conteos daban
# cero y la conversión salía 100%. La fase arregla eso de raíz y para siempre.
FASE_ARMADA = "armada"
FASE_ENVIADA = "enviada"
FASE_GANADA = "ganada"
FASE_PERDIDA = "perdida"

FASES_COT = (
    (FASE_ARMADA, "Armada — todavía no se le manda al cliente"),
    (FASE_ENVIADA, "Enviada — el cliente la tiene, esperamos respuesta"),
    (FASE_GANADA, "Ganada — el cliente dijo que sí"),
    (FASE_PERDIDA, "Perdida — ya no va"),
)

# Fases que cuentan como oportunidad todavía viva.
FASES_VIVAS = (FASE_ARMADA, FASE_ENVIADA)

# slug → (label, color, orden, terminal, fase). Sembrado como sistema=True en la
# migración 0008. Editable desde la UI de Gerencia sin tocar código.
ESTADOS_COT_SEED = (
    ("generada", "Generada", "#0ba5ec", 10, False, FASE_ARMADA),
    ("enviada",  "Enviada",  "#465fff", 20, False, FASE_ENVIADA),
    ("aprobada", "Aprobada", "#12b76a", 30, False, FASE_GANADA),
    ("pagada",   "Pagada",   "#7a5af8", 40, True,  FASE_GANADA),
)

# v2: el dict cacheado ahora incluye `fase`.
_CACHE_KEY = "cotizaciones:estados:v2"


class EstadoCotizacion(models.Model):
    """Paso del flujo de una cotización de proyecto, configurable en Gerencia."""

    slug = models.SlugField(max_length=32, unique=True, db_index=True)
    label = models.CharField(max_length=64)
    descripcion = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Qué significa este paso (ayuda para el equipo).",
    )
    color = models.CharField(
        max_length=7, default="#667085", validators=[HEX_COLOR],
        help_text="Color HEX del badge/tracker, ej. #465fff.",
    )
    orden = models.PositiveSmallIntegerField(default=100)
    terminal = models.BooleanField(
        default=False, help_text="Paso final del flujo (ej. Pagada).",
    )
    fase = models.CharField(
        max_length=12, choices=FASES_COT, default=FASE_ARMADA, db_index=True,
        help_text=(
            "Qué significa este paso para el negocio. De aquí salen la "
            "conversión y el conteo de oportunidades perdidas."
        ),
    )
    activo = models.BooleanField(default=True)
    sistema = models.BooleanField(
        default=False, help_text="Sembrado por código; no se puede borrar.",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cotizaciones_estado"
        verbose_name = "estado de cotización"
        verbose_name_plural = "estados de cotización"
        ordering = ["orden", "label"]

    def __str__(self):
        return self.label


# ── Cache de proceso (60s) — evita N+1 en el recuadro y la lista ──────────

def _estados_raw() -> list[dict]:
    """Lista de TODOS los estados como dicts ligeros (cacheada 60s).

    Tolerante a DB no migrada (primer boot, tests aislados)."""
    from django.core.cache import cache
    cacheado = cache.get(_CACHE_KEY)
    if cacheado is not None:
        return cacheado
    try:
        datos = [
            {
                "slug": e.slug, "label": e.label, "color": e.color,
                "orden": e.orden, "terminal": e.terminal, "activo": e.activo,
                "fase": e.fase,
            }
            for e in EstadoCotizacion.objects.all().order_by("orden", "label")
        ]
        cache.set(_CACHE_KEY, datos, 60)
        return datos
    except Exception:  # noqa: BLE001
        return []


def estados_cot_activos() -> list[dict]:
    """Estados activos, ordenados — para el dropdown y el pizza-tracker."""
    return [e for e in _estados_raw() if e["activo"]]


def mapa_estados_cot() -> dict[str, dict]:
    """{slug: {label, color, orden, terminal, activo}} para label/color por slug."""
    return {e["slug"]: e for e in _estados_raw()}


def invalidar_cache_estados_cot() -> None:
    """Llamado desde signals al guardar/borrar EstadoCotizacion."""
    from django.core.cache import cache
    cache.delete(_CACHE_KEY)


# ── Fase: helpers de lectura ──────────────────────────────────────────────

def fase_de(slug: str) -> str:
    """Qué fase es este estado. Un slug desconocido se trata como armada —
    lo prudente: no lo cuenta como ganado ni como perdido."""
    return (mapa_estados_cot().get(slug) or {}).get("fase") or FASE_ARMADA


def slugs_de_fase(*fases: str) -> list[str]:
    """Los slugs que caen en estas fases. Para filtrar querysets sin literales."""
    quiero = set(fases)
    return [e["slug"] for e in _estados_raw() if (e.get("fase") or FASE_ARMADA) in quiero]


def slugs_vivos() -> list[str]:
    """Cotizaciones que todavía pueden convertirse en venta."""
    return slugs_de_fase(*FASES_VIVAS)
