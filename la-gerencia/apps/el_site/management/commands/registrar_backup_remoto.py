"""Persiste una fila en `site_backup_remoto`. Llamado desde `archivo.sh`
tras cada `rsync` a HAL.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from apps.el_site.models import SiteBackupRemoto
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Registra un backup remoto (rsync a HAL). Idempotente: cada llamada inserta una fila."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", required=True, help="Nombre o ruta del archivo replicado.")
        parser.add_argument("--destino", default="HAL")
        parser.add_argument("--estado", choices=["ok", "error"], required=True)

    def handle(self, *args, **opts):
        archivo = opts["archivo"]
        tamano = None
        with contextlib.suppress(OSError):
            tamano = os.path.getsize(archivo) if Path(archivo).exists() else None
        nombre = Path(archivo).name
        SiteBackupRemoto.objects.create(
            archivo=nombre[:240],
            destino=opts["destino"][:80],
            estado=opts["estado"],
            tamano_bytes=tamano,
        )
        self.stdout.write(self.style.SUCCESS(f"Registrado {opts['estado']}: {nombre} → {opts['destino']}"))
