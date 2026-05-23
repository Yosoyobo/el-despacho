"""Emite un evento del Portavoz desde la línea de comandos.

Usado por `mudanza.sh` para emitir `deploy.iniciado` sin necesidad de
una vista HTTP. Útil también para scripts de mantenimiento ad-hoc.

Uso:
    python manage.py emitir_evento deploy.iniciado --payload '{"commit_sha":"abc"}'
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Emite un evento del Portavoz (encolado en Redis para el worker n8n)."

    def add_arguments(self, parser):
        parser.add_argument("tipo", help='Tipo de evento (ej. "deploy.iniciado").')
        parser.add_argument(
            "--payload", default="{}",
            help="JSON con el payload del evento (default '{}').",
        )

    def handle(self, *args, **opts):
        tipo = opts["tipo"]
        try:
            payload = json.loads(opts["payload"])
            if not isinstance(payload, dict):
                raise ValueError("payload debe ser un objeto JSON.")
        except (json.JSONDecodeError, ValueError) as exc:
            raise CommandError(f"--payload inválido: {exc}") from exc

        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        try:
            emitir(EventoPortavoz(
                tipo=tipo,
                actor_id=None,
                actor_email=payload.pop("actor_email", None),
                payload=payload,
            ))
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Fallo emitiendo evento: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Evento emitido: {tipo}"))
