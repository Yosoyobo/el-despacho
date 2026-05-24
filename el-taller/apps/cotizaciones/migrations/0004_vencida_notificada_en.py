from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0003_variacion_descripcion_opcional"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="vencida_notificada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
