"""Seed del slot estructural `reglas_operativas` en PromptVoz (S-Chalan-Voz-Usuario).

Una fila vacía adicional para que `/chalanes/prompts/` muestre el textarea de
reglas operativas avanzadas. Vacío = comportamiento por defecto. Idempotente.
"""

from django.db import migrations

SLOT = "reglas_operativas"


def seed(apps, schema_editor):
    PromptVoz = apps.get_model("chalanes", "PromptVoz")
    PromptVoz.objects.get_or_create(clave=SLOT, defaults={"contenido": ""})


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "PromptVoz").objects.filter(clave=SLOT).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0007_prompt_voz"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
