"""Los archivos de una factura más allá de su CFDI (S-Tickets-Oct14).

Sólo esquema: tabla nueva, sin datos (§14 Bug I). Escrita a mano porque
`makemigrations` arrastra cambios de estado de otras apps que no son de este
sprint.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0013_cfdi_egreso_proveedor"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FacturaAdjunto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("archivo_id", models.CharField(max_length=255)),
                ("nombre", models.CharField(max_length=255)),
                ("mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("tamano_bytes", models.PositiveBigIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "factura",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adjuntos",
                        to="facturacion.factura",
                    ),
                ),
                (
                    "subido_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="factura_adjuntos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "facturacion_adjunto",
                "ordering": ["creado_en", "pk"],
            },
        ),
    ]
