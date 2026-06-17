"""Fase 3 — Proactividad de El Chalán.

Agrega el origen `chalan_proactivo` al Dictado y crea `PropuestaChalan` (la
bandeja de sugerencias proactivas, idempotente por `(usuario, clave_dedup)`).

Migración reescrita a mano: makemigrations metía operaciones espurias
(rename de índices históricos, AlterField de `id` a BigAutoField, AlterField de
`dictadoaccion.tipo`) que NO corresponden a este sprint (ver CLAUDE.md §14 y la
nota de migraciones a mano). Solo van los cambios reales.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_dictado", "0004_mensaje_chat_adjunto"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
                    ("chalan_proactivo", "Sugerencia proactiva de El Chalán"),
                ],
                default="sala_juntas", max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="PropuestaChalan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(db_index=True, max_length=40)),
                ("clave_dedup", models.CharField(db_index=True, max_length=120)),
                ("titulo", models.CharField(max_length=160)),
                ("cuerpo", models.TextField(blank=True, default="")),
                ("url", models.CharField(blank=True, default="", max_length=300)),
                ("chalan", models.CharField(blank=True, default="", max_length=30)),
                ("estado", models.CharField(
                    choices=[("pendiente", "Pendiente"), ("vista", "Vista"),
                             ("aplicada", "Aplicada"), ("descartada", "Descartada")],
                    db_index=True, default="pendiente", max_length=20)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("resuelta_en", models.DateTimeField(blank=True, null=True)),
                ("dictado", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="propuestas", to="el_dictado.dictado")),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="propuestas_chalan", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "el_dictado_propuesta_chalan",
                "ordering": ["-creada_en"],
            },
        ),
        migrations.AddIndex(
            model_name="propuestachalan",
            index=models.Index(fields=["usuario", "estado"], name="el_dictado__usuario_09b6b0_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="propuestachalan",
            unique_together={("usuario", "clave_dedup")},
        ),
    ]
