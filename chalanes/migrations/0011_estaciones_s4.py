"""Siembra las 4 estaciones de S4 en CuadroChalanes.

S4 — IA (Los Chalanes, casos de uso): `cotizaciones` (Redactar cotización),
`gastos` (Categorizar gasto), `comunicacion` (Resumir actividad de proyecto),
`precio` (Sugerir precio). Idempotente: no pisa ajustes del super_admin.
Valores espejo de `chalanes/estaciones.py::ESTACIONES`.
"""

from django.db import migrations

# (estacion, proveedor, modelo, descripcion)
ESTACIONES_S4 = [
    ("cotizaciones", "anthropic", "claude-haiku-4-5",
     "Genera el cuerpo formal de una cotización para el cliente."),
    ("gastos", "deepseek", "deepseek-chat",
     "Asigna categoría contable a un gasto descrito en texto libre."),
    ("comunicacion", "anthropic", "claude-haiku-4-5",
     "Resume la actividad reciente de un proyecto (eventos, comentarios y tareas) en un párrafo ejecutivo."),
    ("precio", "anthropic", "claude-haiku-4-5",
     "Estima rango de precio con base en histórico de proyectos similares."),
]


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    for estacion, proveedor, modelo, desc in ESTACIONES_S4:
        if CuadroChalanes.objects.filter(estacion=estacion).exists():
            continue
        CuadroChalanes.objects.create(
            estacion=estacion, proveedor=proveedor, modelo=modelo,
            descripcion=desc, requiere_vision=False,
        )


def unseed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CuadroChalanes.objects.filter(
        estacion__in=[e[0] for e in ESTACIONES_S4]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0010_redaccion_asistida_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
