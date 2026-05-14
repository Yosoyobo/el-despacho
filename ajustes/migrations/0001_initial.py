import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("cuentas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Credencial",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("clave", models.SlugField(max_length=80, unique=True)),
                ("valor_cifrado", models.TextField()),
                ("actualizada_en", models.DateTimeField(auto_now=True)),
                (
                    "actualizada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "ajustes_credencial",
                "ordering": ["clave"],
            },
        ),
    ]
