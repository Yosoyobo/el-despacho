from django.db import migrations, models


class Migration(migrations.Migration):
    """Cotizaciones versionadas por proyecto (recuadro «Cotizaciones» del
    detalle de proyecto). Agrega `version` y `pagada_en`, y suma los estados
    `generada` y `pagada` al flujo generada → enviada → aprobada → pagada."""

    dependencies = [
        ("cotizaciones", "0006_cotizacion_pdf"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="version",
            field=models.PositiveIntegerField(default=0, db_index=True),
        ),
        migrations.AddField(
            model_name="cotizacion",
            name="pagada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="cotizacion",
            name="estado",
            field=models.CharField(
                choices=[
                    ("borrador", "Borrador"),
                    ("generada", "Generada"),
                    ("enviada", "Enviada"),
                    ("aprobada", "Aprobada"),
                    ("pagada", "Pagada"),
                    ("rechazada", "Rechazada"),
                    ("anulada", "Anulada"),
                ],
                db_index=True,
                default="borrador",
                max_length=20,
            ),
        ),
    ]
