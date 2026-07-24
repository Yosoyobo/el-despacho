from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cartera", "0006_cliente_geo"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="razon_social_fiscal",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
