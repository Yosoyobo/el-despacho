"""LecturaBuzon — lectura por usuario (S-Chalanes-UX #3)."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buzon', '0004_estado_buzon'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LecturaBuzon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('leido_en', models.DateTimeField(auto_now_add=True)),
                ('mensaje', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lecturas', to='buzon.mensajebuzon')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lecturas_buzon', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'buzon_lectura',
            },
        ),
        migrations.AddIndex(
            model_name='lecturabuzon',
            index=models.Index(fields=['usuario', 'mensaje'], name='buzon_lectu_usuario_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='lecturabuzon',
            unique_together={('usuario', 'mensaje')},
        ),
    ]
