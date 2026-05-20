"""Seed del catálogo de cuentas contables. Idempotente vía update_or_create."""

from django.db import migrations


def seed(apps, schema_editor):
    CuentaContable = apps.get_model("contaduria", "CuentaContable")
    from apps.contaduria.cuentas_seed import CUENTAS_SEED
    for codigo, nombre, tipo, naturaleza, slot, descripcion in CUENTAS_SEED:
        CuentaContable.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "tipo": tipo,
                "naturaleza": naturaleza,
                "slot": slot,
                "descripcion": descripcion,
                "activa": True,
            },
        )


def reverse(apps, schema_editor):
    CuentaContable = apps.get_model("contaduria", "CuentaContable")
    from apps.contaduria.cuentas_seed import CUENTAS_SEED
    CuentaContable.objects.filter(codigo__in=[c[0] for c in CUENTAS_SEED]).delete()


class Migration(migrations.Migration):
    dependencies = [("contaduria", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse)]
