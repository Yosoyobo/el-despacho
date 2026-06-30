"""S-LC-Feedback-V13 (Oscar): paso «Anticipo» en el pizza-tracker de la
cotización del proyecto.

Cuando la cotización del proyecto se mueve a este estatus, el sistema avisa al
equipo de finanzas y ofrece registrar el ingreso del anticipo (50% u otro
monto) ligado al proyecto. El paso es `sistema=True` (no se borra) pero el
super_admin lo puede renombrar/reordenar/desactivar desde Gerencia.

Idempotente vía update_or_create por slug.
"""

from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):
    EstadoCotizacion = apps.get_model("cotizaciones", "EstadoCotizacion")
    EstadoCotizacion.objects.update_or_create(
        slug="anticipo",
        defaults={
            "label": "Anticipo",
            "color": "#f79009",
            "orden": 35,  # entre Aprobada (30) y Pagada (40)
            "terminal": False,
            "activo": True,
            "sistema": True,
        },
    )


def reverse(apps, schema_editor):
    EstadoCotizacion = apps.get_model("cotizaciones", "EstadoCotizacion")
    EstadoCotizacion.objects.filter(slug="anticipo", sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [("cotizaciones", "0008_estado_cotizacion")]
    operations = [migrations.RunPython(seed, reverse)]
