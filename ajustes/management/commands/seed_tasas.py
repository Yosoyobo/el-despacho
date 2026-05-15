"""Siembra tasas impositivas iniciales (México). Idempotente.

- IVA 16% trasladado, default
- IVA 8% Frontera trasladado
- Retención ISR 10%
- Retención IVA 10.67%
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from ajustes.models import TasaImpositiva

TASAS_INICIALES = [
    {"nombre": "IVA 16%", "porcentaje": Decimal("16.00"), "tipo": "trasladado", "aplicable_default": True, "orden": 10},
    {"nombre": "IVA 8% Frontera", "porcentaje": Decimal("8.00"), "tipo": "trasladado", "aplicable_default": False, "orden": 20},
    {"nombre": "Retención ISR 10%", "porcentaje": Decimal("10.00"), "tipo": "retencion", "aplicable_default": False, "orden": 30},
    {"nombre": "Retención IVA 10.67%", "porcentaje": Decimal("10.67"), "tipo": "retencion", "aplicable_default": False, "orden": 40},
]


class Command(BaseCommand):
    help = "Siembra tasas impositivas iniciales (idempotente)."

    def handle(self, *args, **opts):
        creadas = 0
        for spec in TASAS_INICIALES:
            _, created = TasaImpositiva.objects.get_or_create(
                nombre=spec["nombre"],
                defaults={k: v for k, v in spec.items() if k != "nombre"},
            )
            creadas += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Tasas impositivas: {creadas} nuevas, {len(TASAS_INICIALES) - creadas} ya existían."
        ))
