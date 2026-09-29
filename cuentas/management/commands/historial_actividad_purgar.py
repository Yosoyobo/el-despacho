"""Borra el historial de actividad de más de un año (2026-09-29, decisión de Oscar).

Corre cada noche desde `infra/cron/el-despacho.cron`. `--dry-run` sólo cuenta.
`--dias` existe para probar; el valor que manda es `RETENCION_DIAS`.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from lib import historial_actividad


class Command(BaseCommand):
    help = "Borra el historial de actividad más viejo que la retención (un año)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Sólo cuenta, no borra.")
        parser.add_argument("--dias", type=int, default=historial_actividad.RETENCION_DIAS)

    def handle(self, *args, **opts):
        dias = max(int(opts["dias"]), 1)
        n = historial_actividad.purgar(dias=dias, en_seco=opts["dry_run"])
        verbo = "Se borrarían" if opts["dry_run"] else "Se borraron"
        self.stdout.write(f"{verbo} {n} renglones del historial de más de {dias} días.")
