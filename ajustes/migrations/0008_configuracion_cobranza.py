import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0007_plantilla_correo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionCobranza',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activa', models.BooleanField(default=False, help_text='Si está activa, el cron diario manda recordatorios a los clientes.')),
                ('dias_entre_recordatorios', models.PositiveSmallIntegerField(default=7, help_text='Días mínimos entre un recordatorio y el siguiente para la misma factura.')),
                ('max_recordatorios', models.PositiveSmallIntegerField(default=4, help_text='Máximo de recordatorios por factura (0 = sin límite).')),
                ('recordar_pre_vencimiento_dias', models.PositiveSmallIntegerField(default=0, help_text='Días ANTES del vencimiento para un aviso anticipado (0 = solo después de vencer).')),
                ('incluir_pdf', models.BooleanField(default=False, help_text='Adjuntar el PDF de la factura al recordatorio (requiere Google Drive).')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('actualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_cobranza_actualizadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'configuración de cobranza',
                'verbose_name_plural': 'configuración de cobranza',
                'db_table': 'ajustes_configuracion_cobranza',
            },
        ),
    ]
