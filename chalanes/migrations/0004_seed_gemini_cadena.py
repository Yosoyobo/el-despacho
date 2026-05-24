"""Siembra fila de Gemini en CadenaFallback con la siguiente prioridad libre.

S-Demo-Pre-Showcase (2026-05-24). Gemini pasó de skeleton a adapter
activo; este seed lo agrega al fallback global. Idempotente igual que
MiMo (0003).
"""

from django.db import migrations


def seed_gemini(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    if CadenaFallback.objects.filter(proveedor="gemini").exists():
        return
    max_prio = CadenaFallback.objects.order_by("-prioridad").values_list(
        "prioridad", flat=True,
    ).first() or 0
    CadenaFallback.objects.create(
        proveedor="gemini", prioridad=max_prio + 1, activo=True,
    )


def unseed_gemini(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    CadenaFallback.objects.filter(proveedor="gemini").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0003_seed_mimo_cadena"),
    ]

    operations = [
        migrations.RunPython(seed_gemini, unseed_gemini),
    ]
