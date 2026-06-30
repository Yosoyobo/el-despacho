from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0005_uppercase_razon_social'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='lat',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cliente',
            name='lng',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
