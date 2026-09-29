# Ajustes del portal (S5): «Entrar con Google» apagado por default. Sólo esquema;
# la fila única se crea al leer (ConfiguracionPortal.obtener), no aquí (Bug I).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0002_seed_permisos_recepcion'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionPortal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('google_activo', models.BooleanField(default=False, help_text='Enseñar «Entrar con Google» en el portal. Antes, registra https://recepcion.learningcenter.mx/auth/google/callback en Google Cloud Console. Sólo entra quien ya tiene acceso: Google nunca da de alta a nadie.')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'configuración del portal',
                'verbose_name_plural': 'configuración del portal',
                'db_table': 'portal_configuracion',
            },
        ),
    ]
