# La llave del cliente ya no caduca ni se gasta (anulado_en, token cifrado, usos)
# y la papelería que entrega por el portal (DocumentoCliente + sus ajustes).
# Sólo esquema: revivir las llaves viejas va aparte en 0005 (§14 Bug I).

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import portal.models.configuracion


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0008_razones_sociales'),
        ('facturacion', '0013_cfdi_egreso_proveedor'),
        ('portal', '0003_configuracion_portal'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionportal',
            name='csf_vigencia_dias',
            field=models.PositiveSmallIntegerField(default=30, help_text='Días máximos de antigüedad de la Constancia de Situación Fiscal.', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(730)]),
        ),
        migrations.AddField(
            model_name='configuracionportal',
            name='documentos_activo',
            field=models.BooleanField(default=True, help_text='Enseñar la sección «Documentos» en el portal para que el cliente suba su papelería.'),
        ),
        migrations.AddField(
            model_name='configuracionportal',
            name='documentos_requeridos',
            field=models.JSONField(blank=True, default=portal.models.configuracion._requeridos_default),
        ),
        migrations.AddField(
            model_name='enlaceacceso',
            name='anulado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enlaceacceso',
            name='token_cifrado',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='enlaceacceso',
            name='ultimo_uso_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enlaceacceso',
            name='usos',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='enlaceacceso',
            name='expira_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='enlaceacceso',
            name='motivo',
            field=models.CharField(choices=[('entrada', 'Pedido por la persona'), ('invitacion', 'Invitación del despacho')], default='entrada', max_length=12),
        ),
        migrations.AlterField(
            model_name='eventoportal',
            name='tipo',
            field=models.CharField(choices=[('invitado', 'Invitado por el despacho'), ('revocado', 'Acceso revocado'), ('enlace', 'Se le mandó su enlace'), ('copiado', 'El despacho copió su enlace'), ('cambiado', 'El despacho le cambió el enlace'), ('correo_mal', 'Abrió su enlace con otro correo'), ('entrada', 'Entró'), ('salida', 'Salió'), ('descarga', 'Descargó un documento'), ('aprobacion', 'Aprobó una cotización'), ('rechazo', 'Rechazó una cotización'), ('documento', 'Subió un documento')], db_index=True, max_length=12),
        ),
        migrations.CreateModel(
            name='DocumentoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('comprobante_pago', 'Comprobante de pago'), ('csf', 'Constancia de Situación Fiscal (CSF)'), ('rfc', 'Cédula del RFC'), ('acta_constitutiva', 'Acta constitutiva'), ('poder_notarial', 'Poder del representante legal'), ('identificacion', 'Identificación oficial del representante'), ('comprobante_domicilio', 'Comprobante de domicilio'), ('contrato', 'Contrato firmado'), ('otro', 'Otro documento')], db_index=True, max_length=24)),
                ('archivo', models.CharField(max_length=128)),
                ('nombre_archivo', models.CharField(max_length=200)),
                ('mime', models.CharField(blank=True, default='', max_length=100)),
                ('tamano', models.PositiveIntegerField(default=0)),
                ('espejo_drive', models.CharField(blank=True, default='', max_length=128)),
                ('nota', models.TextField(blank=True, default='')),
                ('estado', models.CharField(choices=[('recibido', 'En revisión'), ('aprobado', 'Revisado'), ('rechazado', 'Rechazado')], db_index=True, default='recibido', max_length=12)),
                ('motivo_rechazo', models.CharField(blank=True, default='', max_length=500)),
                ('revisado_en', models.DateTimeField(blank=True, null=True)),
                ('ia_estado', models.CharField(blank=True, choices=[('', 'No aplica'), ('pendiente', 'El Chalán la está leyendo'), ('lista', 'Leída'), ('sin_leer', 'No se pudo leer')], default='', max_length=10)),
                ('ia', models.JSONField(blank=True, default=dict)),
                ('aplicado_en', models.DateTimeField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('acceso', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos', to='portal.accesocliente')),
                ('aplicado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_cliente_aplicados', to=settings.AUTH_USER_MODEL)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documentos_portal', to='cartera.cliente')),
                ('factura', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comprobantes_cliente', to='facturacion.factura')),
                ('revisado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_cliente_revisados', to=settings.AUTH_USER_MODEL)),
                ('subido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_cliente_subidos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'documento del cliente',
                'verbose_name_plural': 'documentos del cliente',
                'db_table': 'portal_documento',
                'ordering': ['-creado_en'],
                'indexes': [models.Index(fields=['cliente', 'tipo', '-creado_en'], name='portal_doc_cliente_tipo')],
            },
        ),
    ]
