"""Siembra fila de MiMo en CadenaFallback con la siguiente prioridad libre.

Idempotente: si ya existe la fila, no hace nada. La fila se agrega activa por
default; el super_admin la puede desactivar desde /chalanes/ si no quiere que
MiMo entre en el fallback global.
"""

from django.db import migrations


def seed_mimo(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    if CadenaFallback.objects.filter(proveedor="mimo").exists():
        return
    max_prio = CadenaFallback.objects.order_by("-prioridad").values_list(
        "prioridad", flat=True,
    ).first() or 0
    CadenaFallback.objects.create(
        proveedor="mimo", prioridad=max_prio + 1, activo=True,
    )


def unseed_mimo(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    CadenaFallback.objects.filter(proveedor="mimo").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0002_mimo_proveedor"),
    ]

    operations = [
        migrations.RunPython(seed_mimo, unseed_mimo),
    ]
