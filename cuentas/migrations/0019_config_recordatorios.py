"""ConfigRecordatorios — config global de recordatorios de tareas (S-Chalanes-UX #4)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0018_usuario_voz_chalan'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigRecordatorios',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_antes_csv', models.CharField(blank=True, default='', help_text='Días de anticipación separados por coma. Ej. «1,3». Vacío = no avisar antes.', max_length=40)),
                ('avisar_el_dia', models.BooleanField(default=True, help_text='Avisar el día de la entrega.')),
                ('avisar_vencidas', models.BooleanField(default=True, help_text='Avisar mientras la tarea siga vencida (una vez al día).')),
                ('incluir_asignado', models.BooleanField(default=True, help_text='Notificar al responsable de la tarea.')),
                ('incluir_lider', models.BooleanField(default=True, help_text='Notificar al líder del proyecto.')),
                ('incluir_admins', models.BooleanField(default=False, help_text='Notificar también a super_admin y dueño.')),
                ('activo', models.BooleanField(default=True, help_text='Si se apaga, el cron no envía nada.')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Configuración de recordatorios',
                'verbose_name_plural': 'Configuración de recordatorios',
            },
        ),
    ]
