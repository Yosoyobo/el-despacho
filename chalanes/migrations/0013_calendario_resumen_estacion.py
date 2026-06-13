"""Siembra la estación `calendario_resumen` en CuadroChalanes.

S-LC-Feedback-V7 — El Chalán resume el calendario (entregas + tareas próximas).
Texto, no visión. Idempotente: no pisa lo que el super_admin haya ajustado.
"""

from django.db import migrations

ESTACION = "calendario_resumen"
PROVEEDOR = "anthropic"
MODELO = "claude-haiku-4-5"
DESC = "Resume las entregas y tareas próximas del calendario: qué viene, qué urge y la carga del período."


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
        ("chalanes", "0012_enderezar_modelos_cuadro"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
