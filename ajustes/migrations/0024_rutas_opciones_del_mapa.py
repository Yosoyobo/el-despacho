"""Lo que el mapa (OSRM) sabe hacer y no se le estaba pidiendo.

Sólo `AddField`: la fila del singleton nace sola al leerla, así que no hay
datos que sembrar y no aplica el escollo de mezclar esquema con inserciones
en la misma migración (§14 Bug I).

Se quitó a mano el `AlterField` de `credencial.id` que `makemigrations`
agrega siempre — es el espurio de BigAutoField del repo, no un cambio de
este trabajo.
"""

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0023_documento_encabezado_y_marca'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionrutas',
            name='acera_del_cliente',
            field=models.BooleanField(default=False, help_text='Llegar por la acera donde está el cliente, para no cruzar la avenida con la caja. Alarga un poco la ruta cuando toca dar vuelta.'),
        ),
        migrations.AddField(
            model_name='configuracionrutas',
            name='evitar',
            field=models.CharField(blank=True, choices=[('', 'Nada — la ruta más rápida'), ('toll', 'Evitar casetas'), ('motorway', 'Evitar autopistas y vías rápidas'), ('ferry', 'Evitar transbordadores')], default='', help_text='Qué esquivar al trazar la ruta. Evitar casetas suele salir un poco más largo y más lento, pero sin cobro. Sólo se puede elegir una: el mapa no tiene precocidas las combinaciones.', max_length=12),
        ),
        migrations.AddField(
            model_name='configuracionrutas',
            name='factor_trafico',
            field=models.DecimalField(decimal_places=1, default=Decimal('1.0'), help_text='Multiplica los tiempos que calcula el mapa, que son de calle libre y sin tráfico. 1.0 los deja como vienen; 1.5 es hora pico de ciudad. No baja de 1: decir que se llega antes de lo que el mapa cree es al revés de lo que pasa en la calle.', max_digits=3, validators=[django.core.validators.MinValueValidator(Decimal('1.0')), django.core.validators.MaxValueValidator(Decimal('3.0'))]),
        ),
        migrations.AddField(
            model_name='configuracionrutas',
            name='modo',
            field=models.CharField(choices=[('coche', 'Coche o moto'), ('bici', 'Bicicleta')], default='coche', help_text='Con qué se reparte. La bicicleta necesita su propio mapa cargado en el servidor; si no está, se mide como coche.', max_length=8),
        ),
    ]
