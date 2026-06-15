"""Jornada — una fila por (usuario, día) con entrada y salida geolocalizadas."""

from __future__ import annotations

from django.conf import settings
from django.db import models

ESTADO_JORNADA = (
    ("abierta", "Abierta"),
    ("cerrada", "Cerrada"),
)


class Jornada(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jornadas",
    )
    fecha = models.DateField(db_index=True)

    # Entrada — snapshot geo al checar (S-Checador: sin tracking continuo).
    entrada_en = models.DateTimeField(null=True, blank=True)
    entrada_lat = models.FloatField(null=True, blank=True)
    entrada_lng = models.FloatField(null=True, blank=True)
    entrada_precision = models.FloatField(null=True, blank=True, help_text="Metros")
    entrada_sin_geo = models.BooleanField(default=False)
    entrada_offline = models.BooleanField(default=False)
    entrada_uuid = models.CharField(max_length=64, blank=True, default="")

    # Salida.
    salida_en = models.DateTimeField(null=True, blank=True)
    salida_lat = models.FloatField(null=True, blank=True)
    salida_lng = models.FloatField(null=True, blank=True)
    salida_precision = models.FloatField(null=True, blank=True, help_text="Metros")
    salida_sin_geo = models.BooleanField(default=False)
    salida_offline = models.BooleanField(default=False)
    salida_uuid = models.CharField(max_length=64, blank=True, default="")
    # La salida la puso el sistema (no la checó el empleado): jornada que quedó
    # abierta y se cerró al horario de salida default de la compañía (V1.2).
    salida_automatica = models.BooleanField(default=False)

    estado = models.CharField(max_length=10, choices=ESTADO_JORNADA, default="abierta")
    # Minutos de retardo contra el HorarioLaboral vigente al checar entrada.
    retardo_min = models.PositiveIntegerField(default=0)
    # Minutos acumulados de SEGMENTOS previos del mismo día (S-LC-Feedback-V11,
    # decisión Oscar: "si hago más horas de trabajo cuéntalas"). Cuando alguien
    # checa salida y vuelve a checar entrada el mismo día, el segmento cerrado se
    # suma aquí y se abre uno nuevo: así NO se cuenta la pausa (comida) y las
    # horas extra sí se acumulan. `minutos_trabajados` = extra + segmento actual.
    minutos_extra = models.PositiveIntegerField(default=0)
    notas = models.TextField(blank=True, default="")

    # Auditoría de ajuste manual (admin directo o corrección aprobada, V1.3):
    # quién tocó la jornada por última vez y cuándo. NULL = nunca se ajustó.
    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="jornadas_ajustadas",
    )
    ajustado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_jornada"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "fecha"], name="checador_jornada_usuario_fecha"),
        ]
        indexes = [models.Index(fields=["usuario", "fecha"])]

    def __str__(self) -> str:
        return f"Jornada {self.usuario_id} · {self.fecha} ({self.estado})"

    @property
    def minutos_trabajados(self) -> int | None:
        """Suma los segmentos previos (minutos_extra) + el segmento cerrado
        actual. Si la jornada está abierta (sin salida) solo cuenta lo ya
        acumulado de segmentos previos; el segmento en curso no cuenta hasta
        que se checa salida."""
        extra = self.minutos_extra or 0
        if self.entrada_en and self.salida_en:
            seg = int((self.salida_en - self.entrada_en).total_seconds() // 60)
            return extra + max(0, seg)
        return extra or None

    @property
    def reabierta(self) -> bool:
        """True si hay segmentos previos acumulados (la persona checó salida y
        volvió a entrar el mismo día para sumar horas extra)."""
        return bool(self.minutos_extra)

    @property
    def horas_trabajadas(self) -> float | None:
        mins = self.minutos_trabajados
        return round(mins / 60, 2) if mins is not None else None

    @property
    def a_tiempo(self) -> bool:
        return self.retardo_min == 0
