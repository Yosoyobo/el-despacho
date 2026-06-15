"""Aviso del MOMENTO de cumplimiento de un pendiente (S-LC-Feedback-V10).

Cuando un pendiente con HORA llega a su fecha+hora, manda una sola notificación
a la gente asignada (+ líder del proyecto): «Entrega: [Proyecto]» para entregas,
«Vencido: …» para el resto. Idempotente vía `Tarea.aviso_cumplido_en`.

Pensado para correr cada ~15 min en horario laboral (ver crontab en CLAUDE.md §10):
    python manage.py avisar_pendientes_cumplidos
"""

from __future__ import annotations

from datetime import datetime

from apps.el_pizarron.models import Tarea
from django.core.management.base import BaseCommand
from django.utils import timezone


def _destinatarios(tarea):
    """Asignado + líder(es) del proyecto, activos, sin duplicados."""
    por_pk = {}
    if tarea.asignada_a_id and tarea.asignada_a.is_active:
        por_pk[tarea.asignada_a_id] = tarea.asignada_a
    if tarea.proyecto_id:
        for asig in tarea.proyecto.asignaciones.filter(
                rol_en_proyecto="lider", usuario__is_active=True).select_related("usuario"):
            por_pk[asig.usuario_id] = asig.usuario
    return list(por_pk.values())


class Command(BaseCommand):
    help = "Avisa a los asignados cuando un pendiente con hora llega a su fecha+hora."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No envía ni marca — sólo reporta.")

    def handle(self, *args, **opts):
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from apps.taller_home.push_handlers import notificar_pendiente_cumplido

        dry = opts["dry_run"]
        ahora = timezone.localtime()
        terminales = set(slugs_terminales_tarea())
        qs = Tarea.objects.filter(
            fecha_compromiso__isnull=False, hora__isnull=False,
            aviso_cumplido_en__isnull=True,
        ).exclude(estado__in=terminales).select_related("proyecto", "asignada_a")

        enviados = 0
        for tarea in qs:
            due_naive = datetime.combine(tarea.fecha_compromiso, tarea.hora)
            due = timezone.make_aware(due_naive, timezone.get_current_timezone())
            if due > ahora:
                continue  # aún no llega su momento
            destinos = _destinatarios(tarea)
            if dry:
                self.stdout.write(
                    f"[dry] tarea#{tarea.pk} «{tarea.titulo[:40]}» ({tarea.tipo}) "
                    f"venció {due:%Y-%m-%d %H:%M} → {[u.email for u in destinos]}")
                continue
            for u in destinos:
                notificar_pendiente_cumplido(tarea, u)
                enviados += 1
            tarea.aviso_cumplido_en = ahora
            tarea.save(update_fields=["aviso_cumplido_en"])

        if not dry:
            self.stdout.write(f"Avisos de cumplimiento enviados: {enviados}")
