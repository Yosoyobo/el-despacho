from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0009_categorias_proveedor"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="imagen_file_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="servicio",
            name="imagen_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
