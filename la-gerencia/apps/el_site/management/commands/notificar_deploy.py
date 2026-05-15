"""Emite evento Portavoz `deploy.exitoso` o `deploy.rollback` y persiste en
`site_deploy`. Llamado desde el workflow `el-mensajero.yml` (job `mudanza`)
al final del SSH script.
"""

from __future__ import annotations

from apps.el_site.models import SiteDeploy
from django.core.management.base import BaseCommand

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


class Command(BaseCommand):
    help = "Notifica el resultado de un deploy a Portavoz y al historial de El Site."

    def add_arguments(self, parser):
        parser.add_argument("--estado", choices=["ok", "rollback"], required=True)
        parser.add_argument("--commit", default="")
        parser.add_argument("--nota", default="")

    def handle(self, *args, **opts):
        estado = opts["estado"]
        commit = (opts["commit"] or "")[:64]
        nota = (opts["nota"] or "")[:1000]
        SiteDeploy.objects.create(estado=estado, commit=commit, nota=nota)
        tipo = "deploy.exitoso" if estado == "ok" else "deploy.rollback"
        try:
            emitir(EventoPortavoz(
                tipo=tipo,
                actor_id=None,
                actor_email=None,
                payload={"estado": estado, "commit": commit, "nota": nota},
            ))
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.WARNING(f"Portavoz no emitió: {exc}"))
        self.stdout.write(self.style.SUCCESS(f"Deploy {estado} registrado (commit {commit[:8] or '?'})"))
