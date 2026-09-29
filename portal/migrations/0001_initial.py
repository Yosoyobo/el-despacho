# Esquema de los accesos a La Recepción (S5, 2026-09-29). Sólo esquema: los
# permisos se siembran en 0002 (§14 Bug I: esquema O datos, nunca ambos).

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cartera', '0008_razones_sociales'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccesoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('nombre', models.CharField(blank=True, default='', max_length=200)),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('generacion', models.PositiveIntegerField(default=1)),
                ('invitado_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('revocado_en', models.DateTimeField(blank=True, null=True)),
                ('ultima_entrada_en', models.DateTimeField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accesos_portal', to='cartera.cliente')),
                ('contacto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accesos_portal', to='cartera.clientecontacto')),
                ('invitado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accesos_portal_invitados', to=settings.AUTH_USER_MODEL)),
                ('revocado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accesos_portal_revocados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'acceso al portal',
                'verbose_name_plural': 'accesos al portal',
                'db_table': 'portal_acceso_cliente',
                'ordering': ['cliente_id', 'nombre', 'email'],
            },
        ),
        migrations.CreateModel(
            name='EnlaceAcceso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('motivo', models.CharField(choices=[('entrada', 'Entrada pedida por la persona'), ('invitacion', 'Invitación del despacho')], default='entrada', max_length=12)),
                ('creado_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('expira_en', models.DateTimeField()),
                ('usado_en', models.DateTimeField(blank=True, null=True)),
                ('ip_solicitud', models.CharField(blank=True, default='', max_length=64)),
                ('ip_uso', models.CharField(blank=True, default='', max_length=64)),
                ('acceso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enlaces', to='portal.accesocliente')),
            ],
            options={
                'verbose_name': 'enlace de acceso',
                'verbose_name_plural': 'enlaces de acceso',
                'db_table': 'portal_enlace_acceso',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='EventoPortal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('invitado', 'Invitado por el despacho'), ('revocado', 'Acceso revocado'), ('enlace', 'Pidió un enlace de entrada'), ('entrada', 'Entró'), ('salida', 'Salió'), ('descarga', 'Descargó un documento'), ('aprobacion', 'Aprobó una cotización'), ('rechazo', 'Rechazó una cotización')], db_index=True, max_length=12)),
                ('detalle', models.CharField(blank=True, default='', max_length=300)),
                ('ip', models.CharField(blank=True, default='', max_length=64)),
                ('agente', models.CharField(blank=True, default='', max_length=300)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('acceso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eventos', to='portal.accesocliente')),
            ],
            options={
                'verbose_name': 'evento del portal',
                'verbose_name_plural': 'eventos del portal',
                'db_table': 'portal_evento',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddConstraint(
            model_name='accesocliente',
            constraint=models.UniqueConstraint(fields=('cliente', 'email'), name='portal_acceso_cliente_email_unico'),
        ),
        migrations.AddConstraint(
            model_name='accesocliente',
            constraint=models.UniqueConstraint(condition=models.Q(('activo', True)), fields=('email',), name='portal_acceso_email_activo_unico'),
        ),
    ]
