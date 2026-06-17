"""Siembra la estación `aprendizaje_destilado` en CuadroChalanes.

S-Chalan-Aprende-V1 — El Chalán destila aprendizajes reutilizables de su
propio historial de Dictados (clarificaciones + acciones desmarcadas). Es una
tarea de síntesis que corre por cron, así que usa un modelo capaz por defecto
(sonnet); el super_admin puede cambiarlo en /chalanes/. Texto, no visión.
Idempotente: no pisa lo que el super_admin haya ajustado.
"""

from django.db import migrations

ESTACION = "aprendizaje_destilado"
PROVEEDOR = "anthropic"
MODELO = "claude-sonnet-4-6"
DESC = (
    "El Chalán destila aprendizajes reutilizables de su propio historial de "
    "Dictados (clarificaciones y acciones desmarcadas). Corre por cron; las "
    "propuestas se revisan antes de entrar al prompt."
)


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
        ("chalanes", "0015_taller_chat_profundo"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
