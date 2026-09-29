"""Siembra la estación `carga_contable` en CuadroChalanes (S-Carga-Contable).

El Chalán revisa los movimientos de los estados de cuenta que se suben con la
carga contable. Idempotente: no pisa ajustes del super_admin. Valores espejo de
`chalanes/estaciones.py::ESTACIONES`.
"""

from django.db import migrations

ESTACION = ("carga_contable", "anthropic", "claude-haiku-4-5",
            "Clasifica los movimientos de los estados de cuenta que se suben con la carga contable.")


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    estacion, proveedor, modelo, desc = ESTACION
    if not CuadroChalanes.objects.filter(estacion=estacion).exists():
        CuadroChalanes.objects.create(estacion=estacion, proveedor=proveedor, modelo=modelo,
                                      descripcion=desc, requiere_vision=False)


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.filter(estacion=ESTACION[0]).delete()


class Migration(migrations.Migration):
    dependencies = [("chalanes", "0020_seed_grok_cadena")]
    operations = [migrations.RunPython(seed, unseed)]
