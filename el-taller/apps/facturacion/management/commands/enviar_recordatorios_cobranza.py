"""La Cobranza — manda recordatorios de pago a los clientes con factura
vencida (o por vencer). Cron diario.

Uso (ver CLAUDE.md §10):
    python manage.py enviar_recordatorios_cobranza [--dry-run]

Respeta `ajustes.ConfiguracionCobranza`: si NO está activa, no hace nada
(arranca apagada por seguridad). La cadencia y el tope también vienen de
ahí. Idempotente por día gracias a `dias_entre_recordatorios`.
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Manda recordatorios de cobranza a los clientes (vencidas / por vencer)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="No envía ni audita — solo reporta qué facturas tocarían recordatorio.",
        )

    def handle(self, *args, **opts):
        from apps.facturacion import cobranza

        from ajustes.models import ConfiguracionCobranza

        config = ConfiguracionCobranza.obtener()
        if not config.activa and not opts["dry_run"]:
            self.stdout.write("La Cobranza está DESACTIVADA (Ajustes → Cobranza). No se envía nada.")
            return

        hoy = date.today()
        pendientes = cobranza.facturas_a_recordar(hoy=hoy, config=config)
        if not pendientes:
            self.stdout.write("Sin facturas que recordar hoy.")
            return

        if opts["dry_run"]:
            for item in pendientes:
                fac = item["factura"]
                self.stdout.write(
                    f"[dry] {fac.codigo} · {item['tipo']} · {item['dias']}d · "
                    f"saldo {fac.saldo_pendiente} · {fac.cliente.razon_social}"
                )
            self.stdout.write(self.style.WARNING(f"(dry-run) {len(pendientes)} recordatorios pendientes."))
            return

        enviados = 0
        fallidos = 0
        for item in pendientes:
            rec = cobranza.enviar_recordatorio(
                item["factura"], config=config, tipo=item["tipo"],
            )
            if rec.ok:
                enviados += 1
            else:
                fallidos += 1
                self.stderr.write(f"[warn] {item['factura'].codigo}: {rec.detalle}")
        msg = f"Recordatorios enviados: {enviados}" + (f" · fallidos: {fallidos}" if fallidos else "")
        self.stdout.write(self.style.SUCCESS(msg))
