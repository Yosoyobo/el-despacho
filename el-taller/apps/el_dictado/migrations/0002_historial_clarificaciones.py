from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_dictado", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dictado",
            name="historial_clarificaciones",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
