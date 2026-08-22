"""Manda el correo de reenganche a los clientes que llevan tiempo callados.

Lo gobierna una `ReglaCorreo` del evento `cliente_dormido`, que arranca
APAGADA. Sin regla encendida este comando no manda nada, así que ponerlo en el
cron es inofensivo hasta que alguien lo configure en La Gerencia.

La referencia del envío lleva el mes (`cliente:12:2026-08`), así que un cliente
recibe como mucho un correo al mes por regla aunque el cron corra a diario.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Correo de seguimiento a clientes sin proyectos nuevos (regla cliente_dormido)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Enlista a quién le escribiría, sin mandar nada.",
        )

    def handle(self, *args, **opts):
        from lib import reglas_correo

        dry = bool(opts.get("dry_run"))
        resultados = reglas_correo.clientes_dormidos(dry_run=dry)

        if not resultados:
            self.stdout.write(
                "Sin clientes que avisar (o ninguna regla de «cliente dormido» encendida)."
            )
            return

        enviados = sum(1 for r in resultados if r["enviado"])
        for r in resultados:
            marca = "enviado" if r["enviado"] else ("simulado" if dry else "no salió")
            self.stdout.write(f"  {r['cliente']}: {marca}")
        cierre = f"{len(resultados)} cliente(s); {enviados} correo(s) enviados."
        self.stdout.write(self.style.SUCCESS(("[dry-run] " if dry else "") + cierre))
