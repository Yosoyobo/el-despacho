"""Cierra jornadas que quedaron abiertas (S-Checador-V1.2).

Si un empleado no checa salida antes de las 05:00 del día siguiente, su
jornada se cierra al horario de salida default de la compañía de ese día.
Cron diario ~05:10 (ver CLAUDE.md §10).

    python manage.py cerrar_jornadas_abiertas [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cierra jornadas abiertas no checadas antes de las 05:00 del día siguiente."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Reporta cuáles cerraría, sin tocarlas.")

    def handle(self, *args, **opts):
        from apps.checador import services
        from apps.checador.models import Jornada
        from django.utils import timezone

        if opts["dry_run"]:
            import datetime as _dt
            ahora = timezone.now()
            n = 0
            for j in Jornada.objects.filter(entrada_en__isnull=False, salida_en__isnull=True):
                limite = timezone.make_aware(
                    _dt.datetime.combine(j.fecha + _dt.timedelta(days=1), _dt.time(5, 0)))
                if ahora >= limite:
                    self.stdout.write(f"[dry] cerraría jornada {j.pk} ({j.usuario_id}, {j.fecha})")
                    n += 1
            self.stdout.write(self.style.WARNING(f"(dry-run) {n} jornada(s) por cerrar."))
            return

        n = services.cerrar_jornadas_vencidas()
        msg = f"Jornadas cerradas automáticamente: {n}"
        self.stdout.write(self.style.SUCCESS(msg) if n else msg)
