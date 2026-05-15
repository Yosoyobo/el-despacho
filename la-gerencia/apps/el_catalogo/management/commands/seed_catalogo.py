"""Siembra categorías iniciales del Catálogo. Idempotente.

Se invoca en el entrypoint de La Gerencia para que arrancando un Droplet vacío
quede listo el catálogo base. Las categorías son editables desde la UI después.
"""

from apps.el_catalogo.models import CategoriaServicio
from django.core.management.base import BaseCommand

CATEGORIAS_INICIALES = [
    ("Diseño", 10),
    ("Impresión", 20),
    ("Maquila", 30),
    ("Bordado", 40),
    ("Producción", 50),
    ("Otros", 999),
]


class Command(BaseCommand):
    help = "Siembra categorías iniciales de El Catálogo (idempotente)."

    def handle(self, *args, **opts):
        creadas = 0
        for nombre, orden in CATEGORIAS_INICIALES:
            _, created = CategoriaServicio.objects.get_or_create(
                nombre=nombre, defaults={"orden": orden, "activa": True}
            )
            creadas += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"El Catálogo: {creadas} categorías nuevas, {len(CATEGORIAS_INICIALES) - creadas} ya existían."
        ))
