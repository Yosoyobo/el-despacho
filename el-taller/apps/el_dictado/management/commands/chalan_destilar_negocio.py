"""El Chalán destila CONOCIMIENTO del negocio (review-first).

De los hechos reales del negocio saca observaciones durables y las propone como
`ConocimientoNegocio` INACTIVO; el super_admin las revisa/aprueba en La Gerencia
(Chalanes → Conocimiento del negocio). Las aprobadas alimentan las opiniones del
Chalán. Semanal (ver crontab §10) o a mano:

    python manage.py chalan_destilar_negocio [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "El Chalán destila conocimiento durable del negocio; crea propuestas inactivas para revisión."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="No persiste — sólo reporta los candidatos.")

    def handle(self, *args, **opts):
        from apps.el_dictado.destilar_negocio import destilar

        r = destilar(dry_run=opts["dry_run"])
        prefijo = "[dry] " if opts["dry_run"] else ""
        if not r["ok"]:
            self.stdout.write(self.style.WARNING(
                f"{prefijo}No se destiló: motivo={r['motivo']} (provider={r['provider'] or '—'})"))
            return
        cand = r["candidatos"]
        self.stdout.write(
            f"{prefijo}Candidatos {len(cand)} · creados {r['creados']} · "
            f"Chalán={r['provider'] or '—'}")
        for c in cand:
            self.stdout.write(f"  • [{c['ambito']}] {c['observacion']} (peso {c['peso']})")
            if c.get("evidencia"):
                self.stdout.write(self.style.HTTP_INFO(f"      evidencia: {c['evidencia']}"))
        if r["creados"]:
            self.stdout.write(self.style.SUCCESS(
                f"{r['creados']} observaciones creadas (inactivas). Revísalas en "
                "La Gerencia → Chalanes → Conocimiento del negocio."))
