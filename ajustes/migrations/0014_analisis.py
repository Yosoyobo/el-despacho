# S-Chalan-Analisis: umbrales de El Análisis + costo por hora de cada rol.
# Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).

from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0013_ret_iva_honorarios_tasa'),
        ('cuentas', '0040_intento_acceso'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionAnalisis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_silencio_cotizacion', models.PositiveSmallIntegerField(default=45, help_text='Días sin respuesta desde que se envió una cotización para darla por perdida. Cero = nunca se da por perdida sola.')),
                ('marcar_perdidas_solo', models.BooleanField(default=False, help_text='Si está prendido, la cotización enfriada cambia de estado sola. Apagado (default): sólo se reporta y tú decides.')),
                ('margen_sano_pct', models.DecimalField(decimal_places=2, default=Decimal('50.00'), help_text='% de margen que consideras sano. Debajo de esto el proyecto se marca.', max_digits=5)),
                ('margen_critico_pct', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='% de margen por debajo del cual el proyecto es una alarma roja.', max_digits=5)),
                ('dias_mora_alerta', models.PositiveSmallIntegerField(default=30, help_text='Días de atraso en un pago para que el Chalán levante la mano.')),
                ('tarifa_hora_default', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Costo por hora que se usa cuando la persona no tiene tarifa por rol. Cero = no se cuesta la mano de obra de esa persona.', max_digits=10)),
                ('prorratear_jornada', models.BooleanField(default=True, help_text='Cuando no hay cronómetro de proyecto, repartir las horas de la jornada en partes iguales entre los proyectos que la persona tocó ese día. El resultado se marca como estimado, no como medido.')),
                ('horas_jornada_tope', models.PositiveSmallIntegerField(default=12, help_text='Tope de horas que se le acreditan a una jornada al prorratear.')),
                ('auto_activar_aprendizajes', models.BooleanField(default=True, help_text='Dejar que el Chalán active solo lo que aprendió cuando está muy seguro. Siempre te avisa y siempre se puede revertir.')),
                ('confianza_minima_auto', models.DecimalField(decimal_places=2, default=Decimal('0.85'), help_text='Qué tan seguro debe estar (0 a 1) para activar algo solo.', max_digits=4)),
                ('dias_ventana_aprendizaje', models.PositiveSmallIntegerField(default=30, help_text='Cuántos días hacia atrás revisa cada vez que aprende.')),
                ('analisis_diario_activo', models.BooleanField(default=True, help_text='Correr la lectura del Chalán cada mañana. Apagado: sólo con el botón.')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('actualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_analisis_actualizadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'configuración de El Análisis',
                'verbose_name_plural': 'configuración de El Análisis',
                'db_table': 'ajustes_configuracion_analisis',
            },
        ),
        migrations.CreateModel(
            name='TarifaRol',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('costo_hora', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Cuánto le cuesta al despacho una hora de este rol.', max_digits=10)),
                ('activo', models.BooleanField(default=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('actualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarifas_actualizadas', to=settings.AUTH_USER_MODEL)),
                ('rol', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tarifa', to='cuentas.rol')),
            ],
            options={
                'verbose_name': 'tarifa por rol',
                'verbose_name_plural': 'tarifas por rol',
                'db_table': 'ajustes_tarifa_rol',
                'ordering': ['rol__nombre'],
            },
        ),
    ]
