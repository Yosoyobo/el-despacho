from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("el_dictado", "0002_historial_clarificaciones"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dictado",
            name="origen",
            field=models.CharField(
                choices=[
                    ("sala_juntas", "Sala de Juntas del Taller"),
                    ("tesoreria_gasto", "Dictado de gasto en Tesorería"),
                    ("taller_chat", "Chat conversacional del Taller"),
                ],
                default="sala_juntas",
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="ConversacionChat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(blank=True, default="", max_length=120)),
                ("archivada", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversaciones_chat",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "el_dictado_conversacion_chat",
                "ordering": ["-actualizado_en"],
            },
        ),
        migrations.CreateModel(
            name="MensajeChat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.IntegerField()),
                ("rol", models.CharField(choices=[("user", "Usuario"), ("bot", "El Chalán")], max_length=10)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("texto", "Texto"),
                            ("herramienta", "Resultado de herramienta"),
                            ("accion", "Propuesta de acción"),
                        ],
                        default="texto",
                        max_length=15,
                    ),
                ),
                ("cuerpo", models.TextField(blank=True, default="")),
                ("nombre_herramienta", models.CharField(blank=True, default="", max_length=40)),
                ("chalan", models.CharField(blank=True, default="", max_length=30)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "conversacion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mensajes",
                        to="el_dictado.conversacionchat",
                    ),
                ),
                (
                    "dictado",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="mensajes_chat",
                        to="el_dictado.dictado",
                    ),
                ),
            ],
            options={
                "db_table": "el_dictado_mensaje_chat",
                "ordering": ["conversacion", "orden"],
            },
        ),
        migrations.AddIndex(
            model_name="conversacionchat",
            index=models.Index(fields=["usuario", "-actualizado_en"], name="el_dictado__usuario_2dd98f_idx"),
        ),
        migrations.AddIndex(
            model_name="mensajechat",
            index=models.Index(fields=["conversacion", "orden"], name="el_dictado__convers_5dd4ce_idx"),
        ),
    ]
