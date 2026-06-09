"""LecturaNovedades + NovedadAnunciada (S-Chalanes-UX #5)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0019_config_recordatorios'),
    ]

    operations = [
        migrations.CreateModel(
            name='NovedadAnunciada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(max_length=90, unique=True)),
                ('anunciada_en', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='LecturaNovedades',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('claves_vistas', models.JSONField(blank=True, default=list)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='lectura_novedades', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
