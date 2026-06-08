"""Tabla PromptVoz + seed de los 5 slots vacíos (voz editable de Los Chalanes).

Crea `chalanes_prompt_voz` y siembra una fila vacía por slot
(`base`, `dictado`, `taller_chat`, `ocr_recibo`, `kpi_dsl`) para que la UI de
`/chalanes/prompts/` muestre los textareas desde el primer arranque. Slot
vacío = comportamiento por defecto (no se inyecta voz). Idempotente.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

SLOTS = ["base", "dictado", "taller_chat", "ocr_recibo", "kpi_dsl"]


def seed(apps, schema_editor):
    PromptVoz = apps.get_model("chalanes", "PromptVoz")
    for clave in SLOTS:
        PromptVoz.objects.get_or_create(clave=clave, defaults={"contenido": ""})


def unseed(apps, schema_editor):
    apps.get_model("chalanes", "PromptVoz").objects.filter(clave__in=SLOTS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chalanes", "0006_ocr_recibo_estacion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PromptVoz",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clave", models.CharField(db_index=True, max_length=40, unique=True)),
                ("contenido", models.TextField(blank=True, default="")),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="prompt_voz_actualizados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "voz de prompt",
                "verbose_name_plural": "voces de prompt",
                "db_table": "chalanes_prompt_voz",
                "ordering": ["clave"],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
