"""Siembra la estación `analisis_negocio` en CuadroChalanes.

S-Chalan-Negocio-V1 — El Chalán opina del negocio (económicos, cobranza,
ventas, márgenes). Síntesis de calidad → sonnet por defecto; el super_admin lo
cambia en /chalanes/. Texto, no visión. Idempotente.
"""

from django.db import migrations

ESTACION = "analisis_negocio"
PROVEEDOR = "anthropic"
MODELO = "claude-sonnet-4-6"
DESC = (
    "El Chalán analiza y opina del negocio (económicos, cobranza, ventas, "
    "márgenes) con datos reales: lo usa el chat y el análisis proactivo que "
    "llega como notificación clickeable."
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
        ("chalanes", "0016_aprendizaje_destilado_estacion"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
