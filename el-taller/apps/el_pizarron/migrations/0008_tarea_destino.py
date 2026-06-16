from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pizarron", "0007_tarea_runner"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarea",
            name="destino_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tarea",
            name="destino_lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tarea",
            name="destino_etiqueta",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
