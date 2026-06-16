"""Mandado — entidad propia para entregas/recolecciones (El Runner).

S-Chalan-Barrido parte 2 (Oscar 2026-06-16). Decisión: **companion 1:1** con
`Tarea`. La entrega/recolección sigue siendo una `Tarea` tipo entrega/recoger
(así nada se rompe: Kanban, "Mis tareas", `Visita.tarea`, comentarios siguen
funcionando igual), y `Mandado` la acompaña 1:1 aportando el **ciclo logístico
de reparto** (por_asignar → asignado → en_camino → entregado/cancelado) y su
propia lista/reporte.

El runner y el destino físicamente viven en la `Tarea` (ya cableados en
`runners.py`, `_mis_tareas`, herramientas del Chalán); `Mandado` los expone como
propiedades para no duplicar estado. Cada Mandado se crea/sincroniza por señal
`post_save` de `Tarea` (ver `signals_mandado.py`).
"""

from __future__ import annotations

from django.db import models

# slug → (label, color). El estado de reparto es independiente del estado de la
# Tarea (pendiente/en_curso/completada): describe la logística de la entrega.
ESTADOS_MANDADO = (
    ("por_asignar", "Por asignar", "#f79009"),
    ("asignado", "Asignado", "#0ba5ec"),
    ("en_camino", "En camino", "#465fff"),
    ("entregado", "Entregado", "#12b76a"),
    ("cancelado", "Cancelado", "#667085"),
)
ESTADO_MANDADO_CHOICES = [(s, lab) for s, lab, _ in ESTADOS_MANDADO]
COLOR_MANDADO = {s: c for s, _, c in ESTADOS_MANDADO}


class Mandado(models.Model):
    tarea = models.OneToOneField(
        "pizarron.Tarea", on_delete=models.CASCADE, related_name="mandado",
    )
    estado = models.CharField(
        max_length=16, choices=ESTADO_MANDADO_CHOICES, default="por_asignar", db_index=True,
    )
    asignado_en = models.DateTimeField(null=True, blank=True)
    en_camino_en = models.DateTimeField(null=True, blank=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    cancelado_en = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pizarron_mandado"
        verbose_name = "mandado"
        verbose_name_plural = "mandados"
        ordering = ["estado", "-creado_en"]

    def __str__(self) -> str:
        return f"Mandado #{self.pk} · {self.tarea.titulo[:40]}"

    # ── Datos delegados a la Tarea (fuente única de runner/destino) ────────────
    @property
    def runner(self):
        return self.tarea.runner

    @property
    def runner_id(self):
        return self.tarea.runner_id

    @property
    def tipo(self) -> str:
        return self.tarea.tipo  # entrega | recoger

    @property
    def titulo(self) -> str:
        return self.tarea.titulo

    @property
    def proyecto(self):
        return self.tarea.proyecto

    @property
    def cliente(self):
        return getattr(self.tarea.proyecto, "cliente", None)

    @property
    def fecha_compromiso(self):
        return self.tarea.fecha_compromiso

    @property
    def destino_lat(self):
        return self.tarea.destino_lat

    @property
    def destino_lng(self):
        return self.tarea.destino_lng

    @property
    def destino_etiqueta(self) -> str:
        return self.tarea.destino_etiqueta or ""

    @property
    def color(self) -> str:
        return COLOR_MANDADO.get(self.estado, "#667085")

    @property
    def es_terminal(self) -> bool:
        return self.estado in ("entregado", "cancelado")
