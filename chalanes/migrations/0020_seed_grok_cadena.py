"""Siembra fila de Grok en CadenaFallback con la siguiente prioridad libre.

S-Chalan-Grok (2026-07-19). Mismo patrón que MiMo (0003) y Gemini (0004): todo
Chalán cloud nuevo se agrega al fallback global por data migration (además del
signal `auto_agregar_a_cadena_fallback`, que solo dispara al guardar la llave).
Idempotente: si ya existe la fila, no hace nada. Se agrega activa por default;
El Reemplazo la salta mientras Grok no tenga API key configurada, y el
super_admin la puede desactivar/reordenar desde /chalanes/cadena/.
"""

from django.db import migrations


def seed_grok(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    if CadenaFallback.objects.filter(proveedor="grok").exists():
        return
    max_prio = CadenaFallback.objects.order_by("-prioridad").values_list(
        "prioridad", flat=True,
    ).first() or 0
    CadenaFallback.objects.create(
        proveedor="grok", prioridad=max_prio + 1, activo=True,
    )


def unseed_grok(apps, schema_editor):
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    CadenaFallback.objects.filter(proveedor="grok").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0019_grok_quitar_ollama"),
    ]

    operations = [
        migrations.RunPython(seed_grok, unseed_grok),
    ]
