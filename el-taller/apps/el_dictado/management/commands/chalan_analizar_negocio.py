"""El Chalán opina del negocio (proactivo).

Por cada dominio (finanzas, cobranza, ventas, márgenes) genera UNA opinión
ejecutiva con datos reales y la reparte como notificación clickeable (abre un
modal con el análisis) a los usuarios con permiso del dominio. Idempotente por
semana. Pensado para correr ~1 vez por semana (ver crontab §10), o a mano:

    python manage.py chalan_analizar_negocio [--dominio finanzas] [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "El Chalán analiza y opina del negocio; reparte la opinión como notificación clickeable."

    def add_arguments(self, parser):
        parser.add_argument("--dominio", choices=["finanzas", "cobranza", "ventas", "margenes"],
                            help="Solo este dominio (default: todos).")
        parser.add_argument("--dry-run", action="store_true",
                            help="No persiste ni notifica — sólo genera y muestra la opinión.")

    def handle(self, *args, **opts):
        from apps.el_dictado.analisis_negocio import analizar_dominio, analizar_todo

        dry = opts["dry_run"]
        prefijo = "[dry] " if dry else ""
        resultados = (
            {opts["dominio"]: analizar_dominio(dominio=opts["dominio"], dry_run=dry)}
            if opts["dominio"] else analizar_todo(dry_run=dry)
        )
        for dom, r in resultados.items():
            if not r["ok"]:
                self.stdout.write(self.style.WARNING(
                    f"{prefijo}{dom}: sin opinión (motivo={r['motivo']})"))
                continue
            if dry:
                self.stdout.write(self.style.SUCCESS(
                    f"{prefijo}{dom}: opinión generada · destinatarios={r.get('destinatarios', 0)}"))
                self.stdout.write(f"  {r['texto']}\n")
            else:
                self.stdout.write(
                    f"{dom}: {r['creadas']} notificaciones repartidas.")
