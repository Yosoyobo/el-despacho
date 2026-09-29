"""El historial de actividad de cada persona (2026-09-29).

Sólo ESQUEMA (§14 Bug I: una migración cambia el esquema o mueve datos, no las
dos cosas). El permiso que decide quién ve el historial de otros se siembra en
la 0053. La tabla nace vacía: no se inventa historia hacia atrás.
"""

from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0051_seed_permiso_contaduria_cargar")]
    operations = [
        migrations.CreateModel(
            name="RegistroActividad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("en", models.DateTimeField()),
                ("tipo", models.CharField(choices=[
                    ("pantalla", "Abrió una pantalla"), ("accion", "Guardó algo"),
                    ("entrada", "Entró"), ("salida", "Cerró sesión"),
                ], max_length=10)),
                ("app", models.CharField(blank=True, default="", max_length=12)),
                ("ruta", models.CharField(blank=True, default="", max_length=300)),
                ("url_name", models.CharField(blank=True, default="", max_length=120)),
                ("kwargs", models.JSONField(blank=True, default=dict)),
                ("destino", models.CharField(blank=True, default="", max_length=300)),
                ("destino_url_name", models.CharField(blank=True, default="", max_length=120)),
                ("metodo", models.CharField(blank=True, default="", max_length=8)),
                ("ip", models.CharField(blank=True, default="", max_length=64)),
                ("agente", models.CharField(blank=True, default="", max_length=300)),
                ("como", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="registros_actividad", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "cuentas_registro_actividad",
                "ordering": ["-en", "-pk"],
                "indexes": [
                    models.Index(fields=["usuario", "-en"], name="idx_regact_usuario_en"),
                    models.Index(fields=["en"], name="idx_regact_en"),
                ],
            },
        ),
    ]
