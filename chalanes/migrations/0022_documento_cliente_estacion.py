"""Siembra la estación `documento_cliente` en CuadroChalanes (portal de clientes).

El Chalán lee la Constancia de Situación Fiscal que un cliente sube en La
Recepción. Con visión: la constancia puede llegar como foto. Idempotente: no pisa
ajustes del super_admin. Valores espejo de `chalanes/estaciones.py::ESTACIONES`.
"""

from django.db import migrations

ESTACION = ("documento_cliente", "anthropic", "claude-haiku-4-5",
            "Lee la Constancia de Situación Fiscal que sube un cliente en el portal.")


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    estacion, proveedor, modelo, desc = ESTACION
    if not CuadroChalanes.objects.filter(estacion=estacion).exists():
        CuadroChalanes.objects.create(estacion=estacion, proveedor=proveedor, modelo=modelo,
                                      descripcion=desc, requiere_vision=True)


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.filter(estacion=ESTACION[0]).delete()


class Migration(migrations.Migration):
    dependencies = [("chalanes", "0021_carga_contable_estacion")]
    operations = [migrations.RunPython(seed, unseed)]
