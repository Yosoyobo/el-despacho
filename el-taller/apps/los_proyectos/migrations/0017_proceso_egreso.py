import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0016_actividad_proyecto'),
        ('tesoreria', '0006_egreso_origen_proyecto'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyectoproductoproceso',
            name='egreso',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='procesos_proyecto',
                to='tesoreria.egreso',
            ),
        ),
    ]
