"""Sprint S-LC-Buzon: nuevo estado terminal 'cerrado' (entregado + pagado +
cobrado). Sembrado como sistema=True. Idempotente.
"""

from django.db import migrations


def seed(apps, schema_editor):
    EstadoProyecto = apps.get_model("proyectos", "EstadoProyecto")
    EstadoProyecto.objects.update_or_create(
        slug="cerrado",
        defaults={
            "label": "Cerrado",
            "color": "badge-brand",
            "orden": 55,
            "terminal": True,
            "activo": True,
            "sistema": True,
        },
    )


def desiembra(apps, schema_editor):
    EstadoProyecto = apps.get_model("proyectos", "EstadoProyecto")
    EstadoProyecto.objects.filter(slug="cerrado").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0012_producto_proveedor_y_procesos"),
    ]

    operations = [
        migrations.RunPython(seed, desiembra),
    ]
