"""La liga CFDI ↔ egreso y el desglose del comprobante (S-Pendientes-Sep28).

Sólo esquema, sobre `facturacion_cfdi_entrante` (§14 Bug I: una migración
cambia el esquema O mueve datos, nunca las dos cosas sobre la misma tabla). Los
CFDI que ya estaban guardados quedan con el desglose vacío y se releen del XML
la primera vez que alguien los resuelve.

Escrita a mano porque `makemigrations` arrastra cambios de estado de otras apps
que no son de este sprint.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0014_servicio_proveedor_principal"),
        ("facturacion", "0012_cfdientrante"),
        ("tesoreria", "0009_egreso_origen_cfdi"),
    ]

    operations = [
        migrations.AddField(
            model_name="cfdientrante",
            name="subtotal",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="descuento",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="iva",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True,
                                      help_text="IVA trasladado a nivel comprobante."),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="retenciones",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True,
                                      help_text="Total de impuestos retenidos."),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="concepto",
            field=models.CharField(blank=True, default="", max_length=300,
                                   help_text="Los conceptos del comprobante, en una línea."),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="pdf_id",
            field=models.CharField(blank=True, default="", max_length=255,
                                   help_text="La representación impresa, si llegó con el correo."),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="proveedor",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="cfdis_recibidos", to="el_catalogo.proveedor",
            ),
        ),
        migrations.AddField(
            model_name="cfdientrante",
            name="egreso",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="cfdi_entrante", to="tesoreria.egreso",
            ),
        ),
        migrations.AlterField(
            model_name="cfdientrante",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente de asignar"),
                    ("ligado", "Ligado"),
                    ("ignorado", "Ignorado"),
                ],
                db_index=True, default="pendiente", max_length=16,
            ),
        ),
    ]
