"""Marca facturas con fecha_vencimiento pasada como vencidas y emite
`factura.vencida` por Portavoz (una sola vez por factura).

Uso (cron diario, ej. 06:05):
    python manage.py marcar_facturas_vencidas

Idempotente: una factura ya notificada no se vuelve a notificar.
Si se registra un cobro total, el cron tampoco la cuenta (estado pasa
a `cobrada_total`).
"""

from __future__ import annotations

from datetime import date

from apps.facturacion.models import Factura
from django.core.management.base import BaseCommand
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


class Command(BaseCommand):
    help = "Marca facturas vencidas y emite factura.vencida."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="No persiste ni emite eventos — sólo reporta.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        hoy = date.today()
        qs = Factura.objects.filter(
            estado__in=["emitida", "cobrada_parcial"],
            fecha_vencimiento__lt=hoy,
            vencida_notificada_en__isnull=True,
        ).select_related("cliente")
        n = 0
        for fac in qs:
            n += 1
            if dry:
                self.stdout.write(
                    f"[dry] {fac.codigo} vencida desde {fac.fecha_vencimiento} "
                    f"(saldo {fac.saldo_pendiente})"
                )
                continue
            fac.vencida_notificada_en = timezone.now()
            fac.save(update_fields=["vencida_notificada_en", "actualizado_en"])
            dias = (hoy - fac.fecha_vencimiento).days
            saldo = float(fac.saldo_pendiente)
            emitir(EventoPortavoz(
                tipo="factura.vencida",
                actor_id=None,
                actor_email=None,
                payload={
                    "factura_id": fac.id,
                    "codigo": fac.codigo,
                    "cliente_id": fac.cliente_id,
                    "fecha_vencimiento": fac.fecha_vencimiento.isoformat(),
                    "dias_vencida": dias,
                    "saldo_pendiente": saldo,
                },
            ))
            # Cobranza automática: push a admins + contador.
            try:
                from apps.taller_home.push_handlers import notificar_factura_vencida
                notificar_factura_vencida(fac, dias_vencida=dias, saldo=saldo)
            except Exception:  # noqa: BLE001 — el push no rompe el cron
                self.stderr.write(f"[warn] push falló para {fac.codigo}")
        msg = f"Facturas vencidas notificadas: {n}"
        self.stdout.write(self.style.SUCCESS(msg) if n else msg)
