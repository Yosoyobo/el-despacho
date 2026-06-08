"""Adjuntos a Drive en Recados legacy (desenmascarado tras conectar Drive).

Solo crea la tabla `recado_adjunto`; no toca las tablas existentes.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recados", "0003_chat"),
        ("cuentas", "__latest__"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecadoAdjunto",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("drive_file_id", models.CharField(max_length=255)),
                ("nombre", models.CharField(max_length=255)),
                ("mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("tamano_bytes", models.PositiveBigIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("recado", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="adjuntos",
                    to="recados.recado",
                )),
                ("subido_por", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    related_name="recado_adjuntos",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "recado_adjunto",
                "ordering": ["creado_en"],
            },
        ),
    ]
