"""Siembra la estación `taller_chat_profundo` (El Relevo, S-Chalan-Agente F1).

El Chalán rutea el razonamiento profundo a esta estación cuando la tarea lo
amerita. Default: anthropic / claude-sonnet-4-6 (más fuerte que el haiku del
chat rápido). Idempotente: no pisa lo que el super_admin haya ajustado.
"""

from django.db import migrations

ESTACION = "taller_chat_profundo"
PROVEEDOR = "anthropic"
MODELO = "claude-sonnet-4-6"
DESC = "El Relevo: cuando El Chalán necesita analizar/planear/sintetizar, rutea el pensamiento a este modelo más potente."


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
        ("chalanes", "0014_checador_visita_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
