"""Scouts proactivos de El Chalán (Fase 3).

Escanea condiciones de negocio accionables (facturas vencidas, proyectos
estancados, mandados sin avance) y genera `PropuestaChalan` idempotentes. El
Chalán redacta cada sugerencia; las que implican cambios quedan como Dictado
PENDIENTE que el usuario confirma — nunca se aplica solo.

Pensado para correr ~1 vez al día (ver crontab §10):
    python manage.py chalan_scouts [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Corre los scouts proactivos de El Chalán (facturas vencidas, proyectos estancados, mandados sin avance)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No genera ni empuja — sólo reporta.")

    def handle(self, *args, **opts):
        from apps.el_dictado.scouts import correr_todos

        salida = correr_todos(dry_run=opts["dry_run"])
        total = sum(v for v in salida.values() if v > 0)
        detalle = " · ".join(f"{k}={v}" for k, v in salida.items())
        prefijo = "[dry] " if opts["dry_run"] else ""
        self.stdout.write(f"{prefijo}Propuestas generadas: {total} ({detalle})")
