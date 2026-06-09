from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0017_presupuesto_ia"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="voz_chalan",
            field=models.TextField(blank=True, default=""),
        ),
    ]
