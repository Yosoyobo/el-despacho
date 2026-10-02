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

    # Checador por actividad (2026-10-01, apps.checador.actividad). Los extremos
    # que puso la actividad y no una checada a mano: la entrada al abrir la
    # jornada con la primera actividad del día; la salida al cerrarla con la
    # última. Lo checado a mano gana: una checada limpia la marca de su extremo.
    entrada_por_actividad = models.BooleanField(default=False)
    salida_por_actividad = models.BooleanField(default=False)
    actividad_primera_en = models.DateTimeField(null=True, blank=True)
    actividad_ultima_en = models.DateTimeField(null=True, blank=True)
    # Última ubicación tomada durante la actividad: es la de la salida al cerrar.
    actividad_lat = models.FloatField(null=True, blank=True)
    actividad_lng = models.FloatField(null=True, blank=True)
    actividad_precision = models.FloatField(null=True, blank=True)
    # Minutos de huecos sin actividad mayores al umbral de la persona, sólo si
    # tiene «Descontar pausas largas». Se restan de las horas trabajadas.
    pausa_min = models.PositiveIntegerField(default=0)

    # Sede donde debió/ocurrió la jornada (S-Checador-V14). La fija el admin al
    # ajustar/registrar la jornada (o se hereda del horario); el empleado puede
    # escribirla a mano al pedir un ajuste.
    sede = models.ForeignKey(
        "checador.SedeLC", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="jornadas",
    )
    sede_texto = models.CharField(max_length=160, blank=True, default="")

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
        pausa = self.pausa_min or 0
        if self.entrada_en and self.salida_en:
            seg = int((self.salida_en - self.entrada_en).total_seconds() // 60)
            return max(0, extra + max(0, seg) - pausa)
        if extra:
            return max(0, extra - pausa)
        return None

    @property
    def por_actividad(self) -> bool:
        """Algún extremo lo puso la actividad (no una checada a mano)."""
        return self.entrada_por_actividad or self.salida_por_actividad

    @property
    def minutos_en_curso(self) -> int | None:
        """Jornada por actividad aún abierta: lo que lleva hasta su última
        actividad (descontadas las pausas). None si no aplica."""
        if self.salida_en or not self.entrada_en or not self.actividad_ultima_en:
            return None
        seg = int((self.actividad_ultima_en - self.entrada_en).total_seconds() // 60)
        return max(0, (self.minutos_extra or 0) + max(0, seg) - (self.pausa_min or 0))

    @property
    def en_curso_texto(self) -> str:
        """«8 h 28 m» de `minutos_en_curso`; vacío si no aplica."""
        mins = self.minutos_en_curso
        if mins is None:
            return ""
        return f"{mins // 60} h {mins % 60:02d} m"

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

    @property
    def sede_label(self) -> str:
        if self.sede_id:
            return getattr(self.sede, "nombre", "")
        return self.sede_texto or ""
