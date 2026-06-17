"""Destila aprendizajes del Chalán desde el historial de Dictados.

El Chalán lee sus propias interpretaciones recientes — sobre todo donde el
usuario lo CORRIGIÓ (clarificaciones) o DESMARCÓ acciones — y propone
aprendizajes reutilizables. Nacen INACTIVOS: el super_admin los revisa y
activa en La Gerencia → Chalanes → Aprendizajes (filtro "Propuestas del
Chalán"). Nunca entran al prompt sin revisión.

Pensado para correr ~1 vez por semana (ver crontab §10), o a mano para
"forzar un análisis ahora":

    python manage.py chalan_destilar_aprendizajes [--dias 30] [--limite 60] [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "El Chalán destila aprendizajes de su historial de Dictados "
        "(clarificaciones + acciones desmarcadas). Crea propuestas inactivas "
        "para revisión en La Gerencia."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=30,
                            help="Ventana de historial a analizar (default 30).")
        parser.add_argument("--limite", type=int, default=60,
                            help="Máximo de dictados a considerar (default 60).")
        parser.add_argument("--dry-run", action="store_true",
                            help="No persiste — sólo reporta los candidatos.")

    def handle(self, *args, **opts):
        from apps.el_dictado.destilar import destilar_aprendizajes

        r = destilar_aprendizajes(
            dias=opts["dias"], limite=opts["limite"], dry_run=opts["dry_run"],
        )
        prefijo = "[dry] " if opts["dry_run"] else ""

        if not r["ok"]:
            self.stdout.write(self.style.WARNING(
                f"{prefijo}No se destiló: motivo={r['motivo']} "
                f"(analizados={r['analizados']}, provider={r['provider'] or '—'})",
            ))
            return

        cand = r["candidatos"]
        self.stdout.write(
            f"{prefijo}Analizados {r['analizados']} dictados · "
            f"candidatos {len(cand)} · creados {r['creados']} · "
            f"Chalán={r['provider'] or '—'}",
        )
        for c in cand:
            self.stdout.write(
                f"  • «{c['frase_o_patron']}» → {c['interpretacion_correcta']} "
                f"(peso {c['peso']})",
            )
            if c.get("razon"):
                self.stdout.write(self.style.HTTP_INFO(f"      razón: {c['razon']}"))

        if r["creados"]:
            self.stdout.write(self.style.SUCCESS(
                f"{r['creados']} propuestas creadas (inactivas). Revísalas en "
                "La Gerencia → Chalanes → Aprendizajes → Propuestas del Chalán.",
            ))
        elif not opts["dry_run"] and not cand:
            self.stdout.write("Sin candidatos nuevos que valga la pena aprender.")
