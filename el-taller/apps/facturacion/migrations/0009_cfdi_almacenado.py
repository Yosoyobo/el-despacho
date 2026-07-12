"""LC #162 — la factura almacena el CFDI (PDF + XML) del PAC en vez de generarlo."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0008_regimen_fiscal"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
            name="xml_file_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="factura",
            name="xml_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="factura",
            name="cfdi_uuid",
            field=models.CharField(
                blank=True, default="", max_length=40,
                help_text="Folio fiscal (UUID) del CFDI timbrado por el PAC.",
            ),
        ),
        migrations.AddField(
            model_name="factura",
            name="cfdi_almacenado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
