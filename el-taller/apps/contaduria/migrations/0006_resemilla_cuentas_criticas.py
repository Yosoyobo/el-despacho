"""Re-seedea cuentas críticas garantizando que estén activas.

Bug #A del sprint S-Finanzas-V2: el reembolso no generaba asiento porque
en algún entorno (probable: Sede tras deploys repetidos) un slot crítico
quedó con activa=False o sin slot asignado.

Esta migración recorre los slots semánticos críticos y para cada uno
busca la cuenta por código y la fuerza a:
  - slot correcto
  - activa=True
  - naturaleza correcta

Idempotente: si los datos ya están bien, no hay efecto.
"""

from django.db import migrations

SLOTS_CRITICOS = [
    ("1.1.01", "caja", "deudora"),
    ("1.1.02", "banco", "deudora"),
    ("1.2.01", "cxc", "deudora"),
    ("1.3.01", "iva_acreditable", "deudora"),
    ("2.1.01", "cxp", "acreedora"),
    ("2.1.03", "reembolsos", "acreedora"),
    ("2.2.01", "iva_trasladado", "acreedora"),
    ("2.2.02", "isr_retenido", "acreedora"),
    ("2.2.03", "iva_retenido_pagar", "acreedora"),
    ("4.1.01", "ingreso_ventas", "acreedora"),
    ("4.2.01", "ingreso_otros", "acreedora"),
    ("5.1.01", "egreso_operativo", "deudora"),
]


def forwards(apps, schema_editor):
    Cuenta = apps.get_model("contaduria", "CuentaContable")
    for codigo, slot, naturaleza in SLOTS_CRITICOS:
        try:
            c = Cuenta.objects.get(codigo=codigo)
        except Cuenta.DoesNotExist:
            # El seed 0002 no la creó (no debería pasar). Skip.
            continue
        cambios = {}
        if c.slot != slot:
            cambios["slot"] = slot
        if not c.activa:
            cambios["activa"] = True
        if c.naturaleza != naturaleza:
            cambios["naturaleza"] = naturaleza
        if cambios:
            for k, v in cambios.items():
                setattr(c, k, v)
            c.save(update_fields=list(cambios.keys()) + ["actualizada_en"])


def reverse(apps, schema_editor):
    # No-op: no es seguro revertir activa o slot a un estado anterior.
    pass


class Migration(migrations.Migration):
    dependencies = [("contaduria", "0005_cuenta_ajuste_captura")]
    operations = [migrations.RunPython(forwards, reverse)]
