"""Marca cotizaciones enviadas con fecha_validez pasada como vencidas
y emite `cotizacion.vencida` por Portavoz (una sola vez por cotización).

Uso (cron diario, ej. 06:00):
    python manage.py marcar_cotizaciones_vencidas

Idempotente: una cotización ya notificada no se vuelve a notificar a
menos que `vencida_notificada_en` se limpie a None manualmente.
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cotizaciones.models import Cotizacion
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


class Command(BaseCommand):
    help = "Marca cotizaciones vencidas y emite cotizacion.vencida."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="No persiste ni emite eventos — sólo reporta.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        hoy = date.today()
        qs = Cotizacion.objects.filter(
            estado="enviada",
            fecha_validez__lt=hoy,
            vencida_notificada_en__isnull=True,
        ).select_related("cliente")
        n = 0
        for cot in qs:
            n += 1
            if dry:
                self.stdout.write(f"[dry] {cot.codigo} venció el {cot.fecha_validez}")
                continue
            cot.vencida_notificada_en = timezone.now()
            cot.save(update_fields=["vencida_notificada_en", "actualizado_en"])
            emitir(EventoPortavoz(
                tipo="cotizacion.vencida",
                actor_id=None,
                actor_email=None,
                payload={
                    "cotizacion_id": cot.id,
                    "codigo": cot.codigo,
                    "cliente_id": cot.cliente_id,
                    "fecha_validez": cot.fecha_validez.isoformat(),
                    "dias_vencida": (hoy - cot.fecha_validez).days,
                },
            ))
        msg = f"Cotizaciones vencidas notificadas: {n}"
        self.stdout.write(self.style.SUCCESS(msg) if n else msg)
