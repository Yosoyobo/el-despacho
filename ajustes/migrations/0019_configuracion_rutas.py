"""La configuración del planeador de rutas, editable desde La Gerencia.

Sólo `CreateModel`: la fila única se crea al LEERLA (`ConfiguracionRutas.obtener`)
y no con una migración de datos. Una migración que inserta en la misma tabla cuyo
índice acaba de crear es lo que tumbó el arranque el 2026-08-23 (§14 Bug I).

También lleva el `AlterField` del campo `evento` de ReglaCorreo, que quedó
pendiente al sumar `mandado_en_camino` al catálogo: es sólo el choices, no toca
datos. Se podó el AlterField espurio del `id` de Credencial (§14).
"""

# Generado con makemigrations y podado — Django 5.1.4 on 2026-08-23 01:56

import datetime
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0018_sembrar_alias_lc'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionRutas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('velocidad_kmh', models.DecimalField(decimal_places=1, default=Decimal('25.0'), help_text='Velocidad promedio para estimar cuánto se tarda entre paradas, en km/h. 25 es un promedio de ciudad con tráfico; súbela si la mayoría de las entregas son por carretera.', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('1')), django.core.validators.MaxValueValidator(Decimal('200'))])),
                ('minutos_por_parada', models.PositiveSmallIntegerField(default=10, help_text='Lo que se tarda en cada parada: estacionarse, bajar, entregar, recabar firma. Se suma a cada tramo del recorrido.', validators=[django.core.validators.MaxValueValidator(240)])),
                ('hora_inicio', models.TimeField(default=datetime.time(9, 0), help_text='A qué hora se supone que arranca la vuelta si ninguna cita obliga antes. Una cita más temprana adelanta la salida sola.')),
                ('max_paradas_por_ruta', models.PositiveSmallIntegerField(default=9, help_text='Tope de paradas por ruta. Nueve es lo que acepta el enlace de Google Maps con paradas intermedias; más que eso, el botón de «abrir en el mapa» deja fuera las últimas.', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(25)])),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'configuración de rutas',
                'verbose_name_plural': 'configuración de rutas',
                'db_table': 'ajustes_config_rutas',
            },
        ),
        migrations.AlterField(
            model_name='reglacorreo',
            name='evento',
            field=models.CharField(choices=[('proyecto_estado', 'Un proyecto cambia de estado'), ('cotizacion_aprobada', 'El cliente aprueba una cotización'), ('mandado_entregado', 'Se marca una entrega como entregada'), ('mandado_en_camino', 'El runner sale con una entrega'), ('cliente_dormido', 'Un cliente lleva tiempo sin proyectos nuevos')], db_index=True, max_length=30),
        ),
    ]
