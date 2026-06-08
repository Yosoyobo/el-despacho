"""Adjuntos a Drive en el chat de Recados (MensajeAdjunto).

Solo crea la tabla `recados_mensaje_adjunto`; no toca tablas existentes.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recados", "0004_recado_adjunto"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MensajeAdjunto",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("drive_file_id", models.CharField(max_length=255)),
                ("nombre", models.CharField(max_length=255)),
                ("mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("tamano_bytes", models.PositiveBigIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("mensaje", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="adjuntos",
                    to="recados.mensaje",
                )),
                ("subido_por", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    related_name="mensaje_adjuntos",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "recados_mensaje_adjunto",
                "ordering": ["creado_en"],
            },
        ),
    ]
