"""Motivos de cancelación de proyecto (LC 2026-08-07, Oscar).

«Cuando se cancele un proyecto, sea donde sea, necesitamos un text input
pequeño donde se pregunte por qué se canceló. Guardar toda la info en una lista
para analizar más adelante.»

El motivo se captura con pastillas de un clic (para que llenarlo no dé flojera y
las estadísticas agrupen solas) más una nota libre. Las pastillas salen de este
catálogo, editable por el super_admin en La Gerencia → Catálogos → Motivos de
cancelación, igual que Estados de proyecto y Estados de tarea.

Capturar el motivo NO es obligatorio: un proyecto se puede cancelar sin decir
por qué y queda listado como «Sin información» con su botón «Agregar +» en
Estadísticas de cancelación.
"""

from django.db import models

# Slug → (label, orden). Sembrados como `sistema=True`: se pueden renombrar y
# apagar desde la UI, pero no borrar (hay proyectos históricos apuntando a ellos).
MOTIVOS_BASE = (
    ("precio", "Precio", 10),
    ("cliente_desistio", "Cliente desistió", 20),
    ("tiempos", "Tiempos", 30),
    ("otro", "Otro", 90),
)


class MotivoCancelacion(models.Model):
    slug = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=60)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    # Un motivo del sistema no se borra (sí se renombra y se apaga).
    sistema = models.BooleanField(default=False)

    class Meta:
        db_table = "proyectos_motivo_cancelacion"
        verbose_name = "motivo de cancelación"
        verbose_name_plural = "motivos de cancelación"
        ordering = ["orden", "label"]

    def __str__(self) -> str:
        return self.label


def motivos_activos():
    """Las pastillas que se ofrecen al cancelar. Defensivo: si la tabla aún no
    existe (migración a medias), devuelve vacío y el modal queda sólo con la
    nota libre."""
    try:
        return list(MotivoCancelacion.objects.filter(activo=True))
    except Exception:  # noqa: BLE001 — un catálogo caído no bloquea cancelar
        return []
