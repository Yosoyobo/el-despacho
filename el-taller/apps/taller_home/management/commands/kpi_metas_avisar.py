"""El aviso de metas en riesgo (S-KPIs-V2, 2026-09-29).

Cada mañana, después de la foto diaria, revisa todas las metas activas y, si
una va en riesgo —atrasada contra lo que se esperaba a estas alturas del
periodo, o pasada de su tope—, avisa por El Interfón UNA sola vez por periodo:
a la persona de la meta, o a quien tiene `kpis.configurar` si es del despacho
o de un cliente.

    python manage.py kpi_metas_avisar [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Avisa por El Interfón las metas de KPI que van en riesgo (una vez por periodo)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Dice qué avisaría, sin mandar ni marcar nada.")

    def handle(self, *args, **opts):
        from apps.taller_home.metas import avisar_en_riesgo

        dry = opts["dry_run"]
        avisadas = avisar_en_riesgo(dry_run=dry)
        prefijo = "[dry] " if dry else ""
        for a in avisadas:
            self.stdout.write(f"  {prefijo}{a['titulo']} → {len(a['para'])} persona(s): {a['cuerpo']}")
        self.stdout.write(self.style.SUCCESS(f"{prefijo}{len(avisadas)} meta(s) en riesgo avisada(s)."))
