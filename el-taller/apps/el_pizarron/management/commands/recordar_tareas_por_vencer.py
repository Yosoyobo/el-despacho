"""Recordatorios de tareas por vencer (S-Chalanes-UX #4).

Cron diario. Lee la config global `cuentas.ConfigRecordatorios` para decidir
cuándo avisar (anticipación / el día / vencidas) y a quién (asignado / líder /
admins). Push vía El Interfón, categoría `tareas` (opt-out por usuario).

Idempotente: cada tarea se recuerda como máximo una vez al día
(`Tarea.ultimo_recordatorio`). Las vencidas se recuerdan a diario mientras
sigan abiertas (si la config lo permite).

Uso (cron, ej. 06:10):
    python manage.py recordar_tareas_por_vencer
"""

from __future__ import annotations

from datetime import date, timedelta

from apps.el_pizarron.models import Tarea
from django.core.management.base import BaseCommand


def _destinatarios(tarea, config):
    """Conjunto de usuarios a notificar (dedup por pk)."""
    por_pk = {}
    if config.incluir_asignado and tarea.asignada_a_id and tarea.asignada_a.is_active:
        por_pk[tarea.asignada_a_id] = tarea.asignada_a
    if config.incluir_lider and tarea.proyecto_id:
        for asig in tarea.proyecto.asignaciones.filter(
                rol_en_proyecto="lider", usuario__is_active=True).select_related("usuario"):
            por_pk[asig.usuario_id] = asig.usuario
    if config.incluir_admins:
        from cuentas.models.usuario import Usuario
        for u in Usuario.objects.filter(is_active=True, rol__in=("super_admin", "dueno")):
            por_pk[u.pk] = u
    return list(por_pk.values())


def _motivo(tarea, hoy, config):
    """Devuelve (motivo, dias) si hoy toca recordar esta tarea, o None."""
    fc = tarea.fecha_compromiso
    if fc is None:
        return None
    if fc < hoy:
        return ("vencida", (fc - hoy).days) if config.avisar_vencidas else None
    if fc == hoy:
        return ("hoy", 0) if config.avisar_el_dia else None
    dias = (fc - hoy).days
    return ("antes", dias) if dias in config.dias_antes else None


class Command(BaseCommand):
    help = "Envía recordatorios de tareas por vencer según la config de Gerencia."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="No envía ni marca — sólo reporta.")

    def handle(self, *args, **opts):
        from cuentas.models import ConfigRecordatorios

        dry = opts["dry_run"]
        config = ConfigRecordatorios.get_solo()
        if not config.activo:
            self.stdout.write("ConfigRecordatorios.activo=False — nada que hacer.")
            return

        hoy = date.today()
        # Sólo tareas abiertas con fecha; cota inferior generosa para vencidas.
        qs = Tarea.objects.exclude(estado="completada").filter(
            fecha_compromiso__isnull=False,
            fecha_compromiso__lte=hoy + timedelta(days=max(config.dias_antes or [0])),
        ).select_related("proyecto", "asignada_a")

        from apps.taller_home.push_handlers import notificar_tarea_recordatorio

        enviados = 0
        for tarea in qs:
            if tarea.ultimo_recordatorio == hoy:
                continue  # ya recordada hoy
            decision = _motivo(tarea, hoy, config)
            if not decision:
                continue
            motivo, dias = decision
            destinos = _destinatarios(tarea, config)
            if not destinos:
                continue
            if dry:
                self.stdout.write(
                    f"[dry] tarea#{tarea.pk} «{tarea.titulo[:40]}» {motivo} "
                    f"→ {[u.email for u in destinos]}")
                continue
            for u in destinos:
                notificar_tarea_recordatorio(tarea, u, motivo=motivo, dias=dias)
                enviados += 1
            tarea.ultimo_recordatorio = hoy
            tarea.save(update_fields=["ultimo_recordatorio"])

        if not dry:
            self.stdout.write(f"Recordatorios enviados: {enviados}")
