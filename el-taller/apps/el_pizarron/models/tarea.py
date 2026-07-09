from django.conf import settings
from django.db import models

# Fallback de labels para estados sembrados (la verdad vive en EstadoTarea;
# esto cubre DB sin migrar y slugs huérfanos). "bloqueada" se eliminó en
# S-LC-Feedback-V6 (migró a "pendiente").
ESTADOS_TAREA = (
    ("pendiente", "Pendiente"),
    ("en_curso", "En curso"),
    ("completada", "Completada"),
)

PRIORIDADES = (
    ("baja", "Baja"),
    ("media", "Media"),
    ("alta", "Alta"),
)

# S-LC-Feedback-V6: tipo de tarea — se refleja en Calendario y "Mis tareas".
TIPOS_TAREA = (
    ("tarea", "Tarea"),
    ("entrega", "Entrega"),
    ("junta", "Junta"),
    ("recoger", "Recoger"),
)


class Tarea(models.Model):
    proyecto = models.ForeignKey("proyectos.Proyecto", on_delete=models.CASCADE, related_name="tareas")
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default="")
    # Estado configurable desde Gerencia (EstadoTarea). Sin choices desde la
    # migración 0004 — el slug valida contra la tabla en el form.
    estado = models.CharField(max_length=32, default="pendiente", db_index=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default="media")
    tipo = models.CharField(max_length=12, choices=TIPOS_TAREA, default="tarea", db_index=True)
    asignada_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tareas_asignadas",
    )
    # LC 2026-07: una tarea puede tener VARIOS responsables. `asignada_a` es el
    # principal (para «Mis tareas», avisos y el runner); `responsables` son los
    # demás. El principal se incluye siempre en `responsables` al guardar.
    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="tareas_corresponsable",
    )
    # S-LC-Proyecto-V2 (Oscar): runner = quien LLEVA (entrega) o RECOGE las
    # cosas. Distinto del responsable (`asignada_a`). Aparece en SUS pendientes.
    # `requiere_runner` lo enciende el tipo entrega/recoger; `runner_auto` marca
    # "que el sistema/El Chalán designe al menos cargado". Diseñado para migrar
    # luego a una entidad propia (Mandado) sin romper este contrato.
    runner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tareas_para_repartir",
    )
    requiere_runner = models.BooleanField(default=False)
    runner_auto = models.BooleanField(default=False)
    runner_asignado_en = models.DateTimeField(null=True, blank=True)
    # S-Chalan-Barrido (Runner por cercanía): ubicación de DESTINO de la entrega/
    # recolección. Si está, la auto-asignación elige al runner más cercano (vs
    # "el menos cargado"). Se puede fijar con pin o se hereda de la última visita
    # geolocalizada al cliente del proyecto. Mismo formato que Visita/Sede.
    destino_lat = models.FloatField(null=True, blank=True)
    destino_lng = models.FloatField(null=True, blank=True)
    destino_etiqueta = models.CharField(max_length=200, blank=True, default="")
    fecha_compromiso = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True, help_text="Hora opcional del compromiso.")
    completada_en = models.DateTimeField(null=True, blank=True)
    # Idempotencia del cron de recordatorios (S-Chalanes-UX #4): fecha del
    # último recordatorio enviado. Evita repetir el mismo día.
    ultimo_recordatorio = models.DateField(null=True, blank=True)
    # S-LC-Feedback-V10: aviso del MOMENTO de cumplimiento (fecha+hora). Se manda
    # una sola vez cuando el pendiente con `hora` llega a su datetime. NULL = aún
    # no avisado.
    aviso_cumplido_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tareas_creadas",
    )

    class Meta:
        db_table = "pizarron_tarea"
        verbose_name = "tarea"
        verbose_name_plural = "tareas"
        ordering = ["estado", "-creado_en"]

    def __str__(self):
        return self.titulo

    @property
    def emoji_tipo(self) -> str:
        """Emoji tipado (LC 2026-07): 🛵 recoger/logística · 💻 tarea operativa ·
        📦 entrega/producción · 📅 junta."""
        return {"recoger": "🛵", "tarea": "💻", "entrega": "📦", "junta": "📅"}.get(self.tipo, "💻")

    @property
    def responsables_todos(self):
        """Responsables efectivos: el principal (`asignada_a`) + los M2M, deduplicados.
        Sirve para display y para las notificaciones."""
        vistos, out = set(), []
        for u in [self.asignada_a] + list(self.responsables.all()):
            if u and u.pk not in vistos:
                vistos.add(u.pk)
                out.append(u)
        return out

    def sincronizar_responsable_principal(self):
        """Garantiza que el principal esté en la M2M (LC 2026-07)."""
        if self.asignada_a_id and not self.responsables.filter(pk=self.asignada_a_id).exists():
            self.responsables.add(self.asignada_a)

    def get_estado_display(self):
        """Label del estado desde EstadoTarea (configurable), con fallback a
        los labels sembrados. Reemplaza al display automático de choices."""
        from apps.el_pizarron.models.estado_tarea import mapa_estados_tarea
        mapa = mapa_estados_tarea()
        if self.estado in mapa:
            return mapa[self.estado]["label"]
        return dict(ESTADOS_TAREA).get(self.estado, self.estado)

    @property
    def duracion_completado(self) -> str:
        """Tiempo que tomó la tarea, de creación → completado (string humano).
        Vacío si aún no está completada. Pedido LC 2026-06-29 (orden y tiempos
        de tareas cerradas)."""
        if not (self.completada_en and self.creado_en):
            return ""
        from django.utils.timesince import timesince
        return timesince(self.creado_en, self.completada_en)

    @property
    def esta_atrasada(self) -> bool:
        """Derivado, NO almacenado: fecha (y hora, si existe) de compromiso ya
        pasó y el estado no es terminal. Se pinta en amarillo como 'Atrasada'."""
        if not self.fecha_compromiso:
            return False
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        if self.estado in slugs_terminales_tarea():
            return False
        from django.utils import timezone
        ahora = timezone.localtime()
        if self.fecha_compromiso < ahora.date():
            return True
        return bool(
            self.fecha_compromiso == ahora.date() and self.hora and self.hora < ahora.time()
        )
