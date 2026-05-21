"""Agrega cuentas para procesadores de pago (Stripe, MercadoPago).

Bug/feature #C del sprint S-Finanzas-V2: los ingresos con
método=stripe|mercadopago hoy se asientan contra la cuenta de Bancos.
Eso es incorrecto: hasta que el operador baja el payout manualmente, el
dinero vive en la cuenta del procesador, no en el banco. Esta migración
crea las cuentas activo·deudora con slots semánticos `stripe_saldo` y
`mp_saldo` para que el signal de Tesorería las use.

Idempotente vía `update_or_create(codigo=...)`.
"""

from django.db import migrations

CUENTAS = [
    # (codigo, nombre, tipo, naturaleza, slot, descripcion)
    ("1.1.03", "Saldo en Stripe", "activo", "deudora", "stripe_saldo",
     "Saldo del balance de Stripe pendiente de bajar a Bancos."),
    ("1.1.04", "Saldo en MercadoPago", "activo", "deudora", "mp_saldo",
     "Saldo en MercadoPago pendiente de bajar a Bancos."),
]


def forwards(apps, schema_editor):
    Cuenta = apps.get_model("contaduria", "CuentaContable")
    for codigo, nombre, tipo, naturaleza, slot, descripcion in CUENTAS:
        Cuenta.objects.update_or_create(
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
    Cuenta = apps.get_model("contaduria", "CuentaContable")
    Cuenta.objects.filter(codigo__in=[c[0] for c in CUENTAS]).delete()


class Migration(migrations.Migration):
    dependencies = [("contaduria", "0006_resemilla_cuentas_criticas")]
    operations = [migrations.RunPython(forwards, reverse)]
