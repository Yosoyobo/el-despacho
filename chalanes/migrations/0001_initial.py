"""Migración inicial de chalanes/ + seeds.

Crea:
- CuadroChalanes (con seed de 8 estaciones)
- ChalanAsignado
- CadenaFallback (con seed: anthropic=1, openai=2, deepseek=3)
"""

from __future__ import annotations

from django.db import migrations, models

SEEDS_CUADRO = [
    # (estacion, proveedor, modelo, descripcion, requiere_vision)
    ("cotizaciones", "anthropic", "claude-haiku-4-5", "Redactar texto de cotización para cliente", False),
    ("gastos", "deepseek", "deepseek-chat", "Categorizar gasto a partir de descripción", False),
    ("comunicacion", "anthropic", "claude-haiku-4-5", "Resumir hilo con cliente", False),
    ("precio", "anthropic", "claude-haiku-4-5", "Sugerir precio para producto/servicio", False),
    ("cliente", "anthropic", "claude-haiku-4-5", "Chat con cliente vía La Recepción (S5)", False),
    ("dictado", "anthropic", "claude-haiku-4-5", "Interpretar dictado en Sala de Juntas", False),
    ("dictado_gasto", "anthropic", "claude-haiku-4-5", "Interpretar dictado de gasto en Tesorería", False),
    ("ocr_recibo", "openai", "gpt-4o-mini", "OCR de recibo (requiere visión)", True),
]

SEEDS_CADENA = [
    # (proveedor, prioridad, activo)
    ("anthropic", 1, True),
    ("openai", 2, True),
    ("deepseek", 3, True),
]


def seed(apps, schema_editor):
    CuadroChalanes = apps.get_model("chalanes", "CuadroChalanes")
    CadenaFallback = apps.get_model("chalanes", "CadenaFallback")
    for estacion, proveedor, modelo, desc, vision in SEEDS_CUADRO:
        CuadroChalanes.objects.update_or_create(
            estacion=estacion,
            defaults={
                "proveedor": proveedor, "modelo": modelo,
                "descripcion": desc, "requiere_vision": vision,
            },
        )
    for proveedor, prioridad, activo in SEEDS_CADENA:
        CadenaFallback.objects.update_or_create(
            proveedor=proveedor,
            defaults={"prioridad": prioridad, "activo": activo},
        )


def reverse_seed(apps, schema_editor):
    apps.get_model("chalanes", "CuadroChalanes").objects.all().delete()
    apps.get_model("chalanes", "CadenaFallback").objects.all().delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [("cuentas", "0005_usuario_slug")]

    operations = [
        migrations.CreateModel(
            name="CuadroChalanes",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("estacion", models.CharField(max_length=40, unique=True, db_index=True)),
                ("proveedor", models.CharField(max_length=30, choices=[
                    ("anthropic", "Chalán Claudio (Anthropic)"),
                    ("openai", "Chalán GPT (OpenAI)"),
                    ("deepseek", "Chalán Chino (Deepseek)"),
                    ("gemini", "Chalán Gemini (Google)"),
                ])),
                ("modelo", models.CharField(max_length=80)),
                ("descripcion", models.CharField(blank=True, default="", max_length=200)),
                ("requiere_vision", models.BooleanField(default=False)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="cuadro_chalanes_actualizados", to="cuentas.usuario",
                )),
            ],
            options={"db_table": "chalanes_cuadro", "ordering": ["estacion"]},
        ),
        migrations.CreateModel(
            name="ChalanAsignado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("estacion", models.CharField(max_length=40, db_index=True)),
                ("proveedor", models.CharField(max_length=30)),
                ("modelo", models.CharField(blank=True, default="", max_length=80)),
                ("motivo", models.CharField(blank=True, default="", max_length=200)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("usuario", models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="chalanes_asignados", to="cuentas.usuario",
                )),
            ],
            options={"db_table": "chalanes_asignado", "ordering": ["usuario_id", "estacion"]},
        ),
        migrations.AddConstraint(
            model_name="chalanasignado",
            constraint=models.UniqueConstraint(fields=("usuario", "estacion"), name="chalan_asignado_unico"),
        ),
        migrations.CreateModel(
            name="CadenaFallback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("proveedor", models.CharField(max_length=30, unique=True)),
                ("prioridad", models.IntegerField(default=100, db_index=True)),
                ("activo", models.BooleanField(default=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "chalanes_cadena_fallback", "ordering": ["prioridad"]},
        ),
        migrations.RunPython(seed, reverse_seed),
    ]
