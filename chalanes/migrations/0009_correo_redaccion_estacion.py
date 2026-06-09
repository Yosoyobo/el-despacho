"""Siembra la estación `correo_redaccion` en CuadroChalanes (El Cartero + IA).

El Chalán redacta/mejora el HTML de las plantillas de correo. Texto, no visión.
Idempotente: no pisa lo que el super_admin haya ajustado.
"""

from django.db import migrations

ESTACION = "correo_redaccion"
PROVEEDOR = "anthropic"
MODELO = "claude-haiku-4-5"
DESC = "Redacta/mejora el HTML de las plantillas de correo respetando las variables."


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
        ("chalanes", "0008_prompt_voz_reglas"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
