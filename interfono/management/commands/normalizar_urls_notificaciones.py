"""Reescribe en base las URLs de notificaciones guardadas con el dominio viejo.

`*.ninomeando.com` → `*.learningcenter.mx` (ver `lib/urls_canonicas.py`).
Revisa `InterfonoEntrega.url` (historial del perfil) e `InterfonoEnvio.url_destino`
(envíos manuales de La Gerencia).

**Es simulacro por defecto**: sólo cuenta y enseña qué cambiaría. Para escribir
hay que pedirlo con `--aplicar`. Nada lo ejecuta solo (ni el deploy ni el cron).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from lib.urls_canonicas import DOMINIOS_HEREDADOS, normalizar_url_heredada

MUESTRA = 10


class Command(BaseCommand):
    help = (
        "Corrige URLs de notificaciones guardadas con el dominio viejo "
        "(ninomeando.com). Simulacro por defecto; --aplicar para escribir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Escribe los cambios. Sin esta bandera sólo informa (simulacro).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Explícito: simulacro (es el comportamiento por defecto).",
        )

    def handle(self, *args, **opts):
        from interfono.models import InterfonoEntrega, InterfonoEnvio

        aplicar = bool(opts["aplicar"]) and not opts["dry_run"]
        self.stdout.write(
            ("APLICANDO cambios" if aplicar else "SIMULACRO (nada se escribe; usa --aplicar)")
            + f" — dominios: {', '.join(f'{v} → {n}' for v, n in DOMINIOS_HEREDADOS.items())}"
        )

        total = 0
        for modelo, campo in ((InterfonoEntrega, "url"), (InterfonoEnvio, "url_destino")):
            filtro = None
            for viejo in DOMINIOS_HEREDADOS:
                q = Q(**{f"{campo}__icontains": viejo})
                filtro = q if filtro is None else filtro | q
            cambios = 0
            muestra: list[tuple[str, str]] = []
            for fila in modelo.objects.filter(filtro).only("pk", campo):
                actual = getattr(fila, campo)
                nueva = normalizar_url_heredada(actual)
                if nueva == actual:
                    continue
                cambios += 1
                if len(muestra) < MUESTRA:
                    muestra.append((actual, nueva))
                if aplicar:
                    modelo.objects.filter(pk=fila.pk).update(**{campo: nueva})
            total += cambios
            self.stdout.write(f"{modelo.__name__}.{campo}: {cambios} por corregir")
            for antes, despues in muestra:
                self.stdout.write(f"    {antes}\n -> {despues}")

        if total and not aplicar:
            self.stdout.write(self.style.WARNING(
                f"{total} fila(s) cambiarían. Ejecuta de nuevo con --aplicar para escribirlas."
            ))
        elif total:
            self.stdout.write(self.style.SUCCESS(f"{total} fila(s) corregidas."))
        else:
            self.stdout.write(self.style.SUCCESS("Nada que corregir."))
