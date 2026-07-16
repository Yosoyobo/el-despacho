"""Arranque de Django para el proceso MCP independiente."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def configurar_django() -> None:
    """Configura el proyecto de El Taller sin pisar settings de tests."""
    raiz = Path(__file__).resolve().parent.parent
    taller = raiz / "el-taller"
    # En ejecución local replica `env_file: .env` de Docker Compose. Nunca
    # reemplaza variables que el proceso ya recibió explícitamente.
    load_dotenv(raiz / ".env", override=False)
    for ruta in (raiz, taller):
        valor = str(ruta)
        if valor not in sys.path:
            sys.path.insert(0, valor)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "el_taller.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()
