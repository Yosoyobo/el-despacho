"""Evento genérico del calendario (S-LC-Feedback-V13).

Tabla `pizarron_evento`. No liga a proyecto; sirve para feriados, vacaciones,
eventos operativos. Puede durar varios días (fecha_inicio→fecha_fin).
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0009_mandado"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Evento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("fecha_inicio", models.DateField(db_index=True)),
                ("fecha_fin", models.DateField(db_index=True)),
                ("color", models.CharField(default="#465fff", max_length=7, validators=[
                    django.core.validators.RegexValidator(
                        message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
                        regex="^#[0-9a-fA-F]{6}$",
                    ),
                ])),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="eventos_creados", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "evento",
                "verbose_name_plural": "eventos",
                "db_table": "pizarron_evento",
                "ordering": ["fecha_inicio", "titulo"],
            },
        ),
    ]
