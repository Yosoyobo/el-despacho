"""Siembra la estación `redaccion_asistida` en CuadroChalanes.

Widget AI 🤖 del Taller (S-Chalanes-UX #2): el botón redacta comentarios,
notas y respuestas. Texto, no visión. Idempotente: no pisa ajustes del
super_admin.
"""

from django.db import migrations

ESTACION = "redaccion_asistida"
PROVEEDOR = "anthropic"
MODELO = "claude-haiku-4-5"
DESC = "El botón 🤖 redacta comentarios, notas y respuestas; resuelve @#$ a datos reales."


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
        ("chalanes", "0009_correo_redaccion_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
