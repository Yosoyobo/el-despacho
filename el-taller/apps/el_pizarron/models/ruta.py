"""Ruta y ParadaRuta — el planeador de rutas de El Runner.

S-Planeador-Rutas (Oscar 2026-08-22): «ya tenemos que lanzar el planeador de
rutas». Decisiones suyas: **una ruta guardada por runner y día** (no una vista
que se recalcula), el planeador **reparte entre los runners disponibles**, la
**hora de la parada es cita fija**, y los **dos** modos de origen conviven
(salir de la sede y regresar / salir de donde está el runner y no volver).

Una `Ruta` es el plan del día de UN runner; sus `ParadaRuta` son los mandados en
el orden en que hay que hacerlos. El mandado, el destino y el runner siguen
viviendo en la `Tarea` (fuente única, igual que en `Mandado`) — aquí sólo se
guarda el ORDEN y una **copia** de lo que se usó para planear.

Por qué la copia: el destino de una tarea puede cambiar después de planear. Sin
snapshot, abrir la ruta de la semana pasada la recalcularía con los datos de hoy
y el historial mentiría. Las coordenadas van en `FloatField` para casar con
`Tarea.destino_lat/lng`, que es de donde salen.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

# slug → (label, color). Espeja el estilo de ESTADOS_MANDADO.
ESTADOS_RUTA = (
    ("borrador", "Borrador", "#f79009"),
    ("despachada", "Despachada", "#465fff"),
    ("cerrada", "Cerrada", "#12b76a"),
    ("cancelada", "Cancelada", "#667085"),
)
ESTADO_RUTA_CHOICES = [(s, lab) for s, lab, _ in ESTADOS_RUTA]
COLOR_RUTA = {s: c for s, _, c in ESTADOS_RUTA}

#: Estados en los que una ruta «ocupa» a su runner ese día. El candado único de
#: la base se apoya en esto: una cancelada no estorba para volver a planear.
ESTADOS_RUTA_VIVOS = ("borrador", "despachada", "cerrada")

ORIGENES_RUTA = (
    ("sede_redonda", "Sale de la sede y regresa a ella"),
    ("runner_abierta", "Sale de donde está el runner y termina en la última parada"),
)

#: Paleta para distinguir las rutas del día en el mapa (una por runner). Se
#: reparte por posición y se repite si hay más runners que colores.
COLORES_RUTA_MAPA = (
    "#465fff", "#12b76a", "#f79009", "#f04438", "#7a5af8",
    "#0ba5ec", "#ee46bc", "#15b79e", "#eaaa08", "#6172f3",
)


class Ruta(models.Model):
    """El plan de reparto de un runner para un día."""

    fecha = models.DateField(db_index=True)
    runner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rutas",
    )
    estado = models.CharField(
        max_length=12, choices=ESTADO_RUTA_CHOICES, default="borrador", db_index=True,
    )

    origen_modo = models.CharField(
        max_length=16, choices=ORIGENES_RUTA, default="sede_redonda",
        help_text="Si la ruta es redonda desde la sede o abierta desde donde está el runner.",
    )
    sede = models.ForeignKey(
        "checador.SedeLC", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rutas", help_text="Sede de salida cuando el modo es redondo.",
    )
    # Snapshot del punto de partida: la sede puede moverse y el runner cambia de
    # posición cada día. Lo que se usó para planear queda aquí.
    origen_lat = models.FloatField(null=True, blank=True)
    origen_lng = models.FloatField(null=True, blank=True)
    origen_etiqueta = models.CharField(max_length=200, blank=True, default="")

    #: Metros estimados en línea recta (no por calles — ver docs del sprint).
    distancia_m = models.PositiveIntegerField(default=0)

    despachada_en = models.DateTimeField(null=True, blank=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    cancelada_en = models.DateTimeField(null=True, blank=True)
    #: Candado de idempotencia del correo al runner (alias runner@).
    correo_enviado_en = models.DateTimeField(null=True, blank=True)

    notas = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="rutas_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pizarron_ruta"
        verbose_name = "ruta"
        verbose_name_plural = "rutas"
        ordering = ["-fecha", "runner_id"]
        constraints = [
            # Una sola ruta viva por runner y día. Va en la BASE porque «una
            # sola» no puede depender de que todos los caminos de escritura se
            # acuerden de revisarlo.
            models.UniqueConstraint(
                fields=["fecha", "runner"],
                condition=models.Q(estado__in=ESTADOS_RUTA_VIVOS),
                name="ruta_una_viva_por_runner_y_dia",
            ),
        ]
        indexes = [models.Index(fields=["fecha", "estado"])]

    def __str__(self) -> str:
        return f"Ruta {self.fecha} · {self.runner}"

    # ── Lecturas ──────────────────────────────────────────────────────────────
    @property
    def color(self) -> str:
        return COLOR_RUTA.get(self.estado, "#667085")

    @property
    def es_redonda(self) -> bool:
        return self.origen_modo == "sede_redonda"

    @property
    def tiene_origen(self) -> bool:
        return self.origen_lat is not None and self.origen_lng is not None

    @property
    def esta_viva(self) -> bool:
        return self.estado in ESTADOS_RUTA_VIVOS

    @property
    def editable(self) -> bool:
        """Sólo un borrador o una despachada se pueden reacomodar."""
        return self.estado in ("borrador", "despachada")

    @property
    def distancia_km(self) -> float:
        return round((self.distancia_m or 0) / 1000.0, 1)

    @property
    def total_paradas(self) -> int:
        return self.paradas.count()

    @property
    def origen_punto(self):
        """(lat, lng) del punto de partida, o None."""
        return (self.origen_lat, self.origen_lng) if self.tiene_origen else None


class ParadaRuta(models.Model):
    """Un mandado dentro de una ruta, en su posición."""

    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name="paradas")
    mandado = models.ForeignKey(
        "pizarron.Mandado", on_delete=models.CASCADE, related_name="paradas_ruta",
    )
    orden = models.PositiveIntegerField(default=0, db_index=True)

    # Snapshot del destino con el que se planeó (ver docstring del módulo).
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    etiqueta = models.CharField(max_length=200, blank=True, default="")

    #: Copiada de `Tarea.hora`. Si existe, la parada es un ANCLA: el orden la
    #: respeta aunque cueste kilómetros (decisión Oscar: la hora es cita fija).
    hora_cita = models.TimeField(null=True, blank=True)
    anclada = models.BooleanField(default=False, db_index=True)

    llegada_estimada = models.TimeField(null=True, blank=True)
    distancia_desde_anterior_m = models.PositiveIntegerField(default=0)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pizarron_ruta_parada"
        verbose_name = "parada de ruta"
        verbose_name_plural = "paradas de ruta"
        ordering = ["orden", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["ruta", "mandado"], name="parada_unica_por_ruta",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.orden}. {self.etiqueta or self.mandado_id}"

    # ── Lecturas ──────────────────────────────────────────────────────────────
    @property
    def punto(self):
        return (self.lat, self.lng) if self.lat is not None and self.lng is not None else None

    @property
    def tarea(self):
        return self.mandado.tarea

    @property
    def distancia_km(self) -> float:
        return round((self.distancia_desde_anterior_m or 0) / 1000.0, 1)

    @property
    def entregada(self) -> bool:
        return self.mandado.estado == "entregado"
