"""Ruta y ParadaRuta — el plan de reparto guardado por runner y día.

S-Planeador-Rutas (Oscar 2026-08-22). Toma el `0015` porque el `0014` es de
S-KPI-BI (los campos de inicio/fin del mandado). Aquél mide el viaje REAL; esto
guarda el viaje PLANEADO.

Limpiada a mano: makemigrations agregaba tres AlterField espurios (id de
comentario y tarea, color de estadotarea) que no son de este sprint (§14).
"""

# Generado con makemigrations y podado — Django 5.1.4 on 2026-08-22 23:01

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checador', '0008_poi_visita_sede_geo'),
        ('pizarron', '0014_mandado_ruta'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Ruta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),
                ('estado', models.CharField(choices=[('borrador', 'Borrador'), ('despachada', 'Despachada'), ('cerrada', 'Cerrada'), ('cancelada', 'Cancelada')], db_index=True, default='borrador', max_length=12)),
                ('origen_modo', models.CharField(choices=[('sede_redonda', 'Sale de la sede y regresa a ella'), ('runner_abierta', 'Sale de donde está el runner y termina en la última parada')], default='sede_redonda', help_text='Si la ruta es redonda desde la sede o abierta desde donde está el runner.', max_length=16)),
                ('origen_lat', models.FloatField(blank=True, null=True)),
                ('origen_lng', models.FloatField(blank=True, null=True)),
                ('origen_etiqueta', models.CharField(blank=True, default='', max_length=200)),
                ('distancia_m', models.PositiveIntegerField(default=0)),
                ('despachada_en', models.DateTimeField(blank=True, null=True)),
                ('cerrada_en', models.DateTimeField(blank=True, null=True)),
                ('cancelada_en', models.DateTimeField(blank=True, null=True)),
                ('correo_enviado_en', models.DateTimeField(blank=True, null=True)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rutas_creadas', to=settings.AUTH_USER_MODEL)),
                ('runner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rutas', to=settings.AUTH_USER_MODEL)),
                ('sede', models.ForeignKey(blank=True, help_text='Sede de salida cuando el modo es redondo.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rutas', to='checador.sedelc')),
            ],
            options={
                'verbose_name': 'ruta',
                'verbose_name_plural': 'rutas',
                'db_table': 'pizarron_ruta',
                'ordering': ['-fecha', 'runner_id'],
            },
        ),
        migrations.CreateModel(
            name='ParadaRuta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveIntegerField(db_index=True, default=0)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lng', models.FloatField(blank=True, null=True)),
                ('etiqueta', models.CharField(blank=True, default='', max_length=200)),
                ('hora_cita', models.TimeField(blank=True, null=True)),
                ('anclada', models.BooleanField(db_index=True, default=False)),
                ('llegada_estimada', models.TimeField(blank=True, null=True)),
                ('distancia_desde_anterior_m', models.PositiveIntegerField(default=0)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('mandado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paradas_ruta', to='pizarron.mandado')),
                ('ruta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paradas', to='pizarron.ruta')),
            ],
            options={
                'verbose_name': 'parada de ruta',
                'verbose_name_plural': 'paradas de ruta',
                'db_table': 'pizarron_ruta_parada',
                'ordering': ['orden', 'pk'],
            },
        ),
        migrations.AddIndex(
            model_name='ruta',
            index=models.Index(fields=['fecha', 'estado'], name='pizarron_ru_fecha_cf63b0_idx'),
        ),
        migrations.AddConstraint(
            model_name='ruta',
            constraint=models.UniqueConstraint(condition=models.Q(('estado__in', ('borrador', 'despachada', 'cerrada'))), fields=('fecha', 'runner'), name='ruta_una_viva_por_runner_y_dia'),
        ),
        migrations.AddConstraint(
            model_name='paradaruta',
            constraint=models.UniqueConstraint(fields=('ruta', 'mandado'), name='parada_unica_por_ruta'),
        ),
    ]
