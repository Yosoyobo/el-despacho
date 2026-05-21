"""Crea cuenta 6.0.01 'Ajustes de captura' para el wizard de ajustes
de saldo. Idempotente: update_or_create no duplica si ya existe.

Naturaleza acreedora (tipo capital) — los ajustes que SUBEN saldo de
cuentas deudoras (caja/bancos) abonan a esta cuenta. Funciona como
contrapartida espejo para correcciones de saldo capturadas por
no-contadores vía wizard.
"""

from django.db import migrations


CODIGO = "6.0.01"


def crear(apps, schema_editor):
    CuentaContable = apps.get_model("contaduria", "CuentaContable")
    CuentaContable.objects.update_or_create(
        codigo=CODIGO,
        defaults={
            "nombre": "Ajustes de captura",
            "tipo": "capital",
            "naturaleza": "acreedora",
            "slot": "ajuste_captura",
            "descripcion": (
                "Contrapartida de ajustes de saldo capturados por "
                "el wizard de movimientos dummy-proof."
            ),
            "activa": True,
        },
    )


def reverse(apps, schema_editor):
    CuentaContable = apps.get_model("contaduria", "CuentaContable")
    CuentaContable.objects.filter(codigo=CODIGO).delete()


class Migration(migrations.Migration):
    dependencies = [("contaduria", "0004_origen_auto_reembolso")]
    operations = [migrations.RunPython(crear, reverse)]
