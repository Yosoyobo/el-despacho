"""Sep28 — los anexos de la cotización (fichas técnicas al final del PDF).

Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).
Sólo crea la tabla; no mueve datos (§14 Bug I).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0019_estado_fase"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CotizacionAnexo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("nombre", models.CharField(max_length=200)),
                ("nombre_original", models.CharField(blank=True, default="",
                                                     max_length=200)),
                ("archivo_clave", models.CharField(max_length=100)),
                ("es_pdf", models.BooleanField(default=True)),
                ("tamano", models.PositiveIntegerField(default=0, help_text="Bytes.")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("cotizacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="anexos", to="cotizaciones.cotizacion")),
                ("subido_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="anexos_cotizacion", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "anexo de cotización",
                "verbose_name_plural": "anexos de cotización",
                "db_table": "cotizaciones_anexo",
                "ordering": ["cotizacion", "orden", "pk"],
            },
        ),
    ]
