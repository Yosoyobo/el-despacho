"""Resumen matutino de El Chalán (Fase 3).

Reúne un roll-up read-only del día (entregas de hoy, facturas vencidas, tareas
vencidas del equipo, mandados en curso, CxC) y le pide a El Chalán que lo redacte
como un digest breve, que se empuja a los admins. Sin acciones — es informativo.
Idempotente por día (`digest:YYYY-MM-DD:<usuario>`).

Pensado para correr una vez en la mañana (ver crontab §10):
    python manage.py chalan_digest_matutino [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera y empuja el resumen matutino de El Chalán a los admins."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No genera ni empuja — sólo reporta.")

    def handle(self, *args, **opts):
        from apps.el_dictado.scouts import correr_digest

        n = correr_digest(dry_run=opts["dry_run"])
        prefijo = "[dry] " if opts["dry_run"] else ""
        self.stdout.write(f"{prefijo}Digest matutino: {n} destinatario(s).")
