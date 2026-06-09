"""ConfigRecordatorios — configuración global de los recordatorios de tareas
por vencer (S-Chalanes-UX #4).

Singleton (pk=1). El super_admin lo edita desde La Gerencia → Ajustes →
Recordatorios. El cron `recordar_tareas_por_vencer` (El Taller) lo lee para
decidir cuándo avisar y a quién.

Default = opción B aprobada por Oscar: avisar el día de la entrega y mientras
siga vencida; destinatarios = el asignado + el líder del proyecto.
"""

from __future__ import annotations

from django.db import models


class ConfigRecordatorios(models.Model):
    # Días de anticipación (CSV de enteros, ej. "1,3"). Vacío = sin anticipación.
    dias_antes_csv = models.CharField(
        max_length=40, blank=True, default="",
        help_text="Días de anticipación separados por coma. Ej. «1,3». Vacío = no avisar antes.",
    )
    avisar_el_dia = models.BooleanField(default=True, help_text="Avisar el día de la entrega.")
    avisar_vencidas = models.BooleanField(
        default=True, help_text="Avisar mientras la tarea siga vencida (una vez al día).")

    incluir_asignado = models.BooleanField(default=True, help_text="Notificar al responsable de la tarea.")
    incluir_lider = models.BooleanField(default=True, help_text="Notificar al líder del proyecto.")
    incluir_admins = models.BooleanField(default=False, help_text="Notificar también a super_admin y dueño.")

    activo = models.BooleanField(default=True, help_text="Si se apaga, el cron no envía nada.")

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cuentas"
        verbose_name = "Configuración de recordatorios"
        verbose_name_plural = "Configuración de recordatorios"

    def __str__(self):
        return "ConfigRecordatorios"

    @property
    def dias_antes(self) -> list[int]:
        out: list[int] = []
        for parte in (self.dias_antes_csv or "").split(","):
            parte = parte.strip()
            if parte.isdigit():
                n = int(parte)
                if n > 0 and n not in out:
                    out.append(n)
        return sorted(out)

    @classmethod
    def get_solo(cls) -> ConfigRecordatorios:
        """Devuelve el singleton (lo crea con defaults si no existe)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
