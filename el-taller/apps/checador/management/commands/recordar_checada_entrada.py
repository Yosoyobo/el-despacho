"""Recordatorio de entrada no checada (S-Checador-V1.2).

Avisa por el Interfón a quien ya pasó su hora de entrada (+ tolerancia) y aún
no registra su entrada del día. Idempotente por día. Cron cada ~30 min en la
franja matutina (ver CLAUDE.md §10).

    python manage.py recordar_checada_entrada [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recuerda checar entrada a quien ya es tarde y no ha checado."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Reporta a quién se le avisaría, sin enviar ni marcar.")

    def handle(self, *args, **opts):
        from apps.checador import services
        from django.utils import timezone

        if opts["dry_run"]:
            # Cálculo sin efectos: reusa la lógica de selección.
            from datetime import timedelta
            local = timezone.localtime()
            hoy = local.date()
            n = 0
            for u in services._checadores_candidatos(hoy):
                h = services.horario_vigente(u, hoy)
                if h is None:
                    continue
                esperado = local.replace(hour=h.hora_entrada.hour, minute=h.hora_entrada.minute,
                                         second=0, microsecond=0)
                if local < esperado + timedelta(minutes=h.tolerancia_min):
                    continue
                if local > esperado + timedelta(hours=6):
                    continue
                from apps.checador.models import Jornada
                j = Jornada.objects.filter(usuario=u, fecha=hoy).first()
                if j and j.entrada_en:
                    continue
                self.stdout.write(f"[dry] avisaría a {u.email}")
                n += 1
            self.stdout.write(self.style.WARNING(f"(dry-run) {n} recordatorio(s) pendientes."))
            return

        enviados = services.recordar_entradas_pendientes()
        msg = f"Recordatorios de entrada enviados: {enviados}"
        self.stdout.write(self.style.SUCCESS(msg) if enviados else msg)
