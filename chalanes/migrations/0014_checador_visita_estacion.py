"""Siembra la estación `checador_visita` en CuadroChalanes.

S-Checador-V14 — El Chalán verifica un registro de POI (visita vs tarea
cumplida) a partir de la nota, el destino y la tarea ligada. Texto, no visión.
Idempotente: no pisa lo que el super_admin haya ajustado.
"""

from django.db import migrations

ESTACION = "checador_visita"
PROVEEDOR = "anthropic"
MODELO = "claude-haiku-4-5"
DESC = "Clasifica un registro del Checador (visita vs tarea cumplida) a partir de la nota, el destino y la tarea ligada."


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    if CuadroChalanes.objects.filter(estacion=ESTACION).exists():
        return
    CuadroChalanes.objects.create(
        estacion=ESTACION, proveedor=PROVEEDOR, modelo=MODELO,
        descripcion=DESC, requiere_vision=False,
    )


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.filter(estacion=ESTACION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0013_calendario_resumen_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
