"""Siembra la estación `taller_chat` en CuadroChalanes (S-Chalan-Chat-V1).

El chat conversacional del Taller usa `analizar(estacion="taller_chat")`.
Sembramos su fila por default (anthropic / claude-haiku-4-5, modelo barato).
Idempotente: solo crea si no existe — si el super_admin ya la ajustó desde
`/chalanes/`, NO la pisa.
"""

from django.db import migrations

ESTACION = "taller_chat"
PROVEEDOR = "anthropic"
MODELO = "claude-haiku-4-5"
DESC = (
    "Chat conversacional: consulta estatus (proyectos, finanzas, gasto IA, "
    "servidor) y propone acciones con confirmación."
)


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    if CuadroChalanes.objects.filter(estacion=ESTACION).exists():
        return
    CuadroChalanes.objects.create(
        estacion=ESTACION,
        proveedor=PROVEEDOR,
        modelo=MODELO,
        descripcion=DESC,
        requiere_vision=False,
    )


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.filter(estacion=ESTACION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0004_seed_gemini_cadena"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
