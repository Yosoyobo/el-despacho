from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0011_servicio_unidad_pz"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="detalles_costo",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
