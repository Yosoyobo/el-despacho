"""Pre-S2b.1: agrega columnas es_fallback/proveedor_original al log y
migra valores cifrados de `anthropic_api_key`/`openai_api_key` (legacy) a
`chalan_anthropic_api_key`/`chalan_openai_api_key`.

Idempotente: si los slots nuevos ya existen, hace update_or_create. Si los
legacy están vacíos, simplemente no copia (no es error).
"""

from __future__ import annotations

from django.db import migrations, models

LEGACY_TO_NUEVO = [
    ("anthropic_api_key", "chalan_anthropic_api_key"),
    ("openai_api_key", "chalan_openai_api_key"),
]


def migrar_slots(apps, schema_editor):
    Credencial = apps.get_model("ajustes", "Credencial")
    for legacy, nuevo in LEGACY_TO_NUEVO:
        viejo = Credencial.objects.filter(clave=legacy).first()
        if not viejo:
            continue
        Credencial.objects.update_or_create(
            clave=nuevo,
            defaults={
                "valor_cifrado": viejo.valor_cifrado,
                "actualizada_por": viejo.actualizada_por,
            },
        )


def reverse_migrar(apps, schema_editor):
    pass  # No revertimos — el slot legacy se queda.


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0003_analista_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="analistalog",
            name="es_fallback",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="analistalog",
            name="proveedor_original",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.RunPython(migrar_slots, reverse_migrar),
    ]
