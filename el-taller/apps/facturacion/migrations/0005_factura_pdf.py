from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0004_factura_concepto"),
    ]

    operations = [
        migrations.AddField(
            model_name="factura",
            name="pdf_file_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="factura",
            name="pdf_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="factura",
            name="pdf_generado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
