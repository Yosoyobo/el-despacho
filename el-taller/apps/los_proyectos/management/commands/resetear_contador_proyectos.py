"""Management command: limpiar proyectos demo y dejar contador en LC-0001.

Uso (en el día del go-live productivo):

    python manage.py resetear_contador_proyectos --confirmar

Sin --confirmar: muestra el plan (cuántos proyectos se borrarían) y aborta.
Con --confirmar: borra TODOS los proyectos y sus dependencias en cascada
(tareas del Pizarrón asociadas, asignaciones, ProyectoProducto, etc.).

El siguiente proyecto que se cree arrancará en LC-0001.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.los_proyectos.models.proyecto import Proyecto


class Command(BaseCommand):
    help = "Borra todos los proyectos y deja el contador en LC-0001 (para go-live)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma la acción destructiva. Sin esto solo muestra el plan.",
        )

    def handle(self, *args, **opts):
        total = Proyecto.objects.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No hay proyectos. Contador ya en LC-0001."))
            return

        if not opts["confirmar"]:
            self.stdout.write(self.style.WARNING(
                f"Se borrarían {total} proyecto(s) y todas sus dependencias en cascada.\n"
                "Pasa --confirmar para ejecutar."
            ))
            return

        with transaction.atomic():
            borrados, detalle = Proyecto.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f"Borrados {borrados} registro(s). Detalle: {detalle}\n"
            "El próximo proyecto que se cree arrancará en LC-0001."
        ))
