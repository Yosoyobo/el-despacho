# La Caja — esquema (Bug I: los datos van en 0002).

import apps.caja.models.link_pago
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cartera', '0008_razones_sociales'),
        ('cotizaciones', '0020_cotizacion_anexo'),
        ('facturacion', '0013_cfdi_egreso_proveedor'),
        ('proyectos', '0038_recolorear_sin_descripcion'),
        ('tesoreria', '0009_egreso_origen_cfdi'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LinkPago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=apps.caja.models.link_pago._token_nuevo, editable=False, max_length=64, unique=True)),
                ('tipo', models.CharField(choices=[('factura', 'Saldo de factura'), ('anticipo', 'Anticipo de cotización'), ('libre', 'Monto libre')], db_index=True, max_length=10)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('concepto', models.CharField(max_length=200)),
                ('moneda', models.CharField(default='MXN', max_length=3)),
                ('estado', models.CharField(choices=[('vigente', 'Vigente'), ('pagado', 'Pagado'), ('anulado', 'Anulado'), ('vencido', 'Vencido')], db_index=True, default='vigente', max_length=10)),
                ('vence_en', models.DateTimeField(default=apps.caja.models.link_pago._vence_default)),
                ('stripe_sesion_id', models.CharField(blank=True, default='', max_length=120)),
                ('stripe_url', models.URLField(blank=True, default='', max_length=1000)),
                ('stripe_sesion_expira', models.DateTimeField(blank=True, null=True)),
                ('mp_preferencia_id', models.CharField(blank=True, default='', max_length=120)),
                ('mp_url', models.URLField(blank=True, default='', max_length=1000)),
                ('pasarela', models.CharField(blank=True, default='', max_length=12)),
                ('pagado_en', models.DateTimeField(blank=True, null=True)),
                ('anulado_en', models.DateTimeField(blank=True, null=True)),
                ('motivo_anulacion', models.CharField(blank=True, default='', max_length=300)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('anulado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago_anulados', to=settings.AUTH_USER_MODEL)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago', to='cartera.cliente')),
                ('cotizacion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago', to='cotizaciones.cotizacion')),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago_creados', to=settings.AUTH_USER_MODEL)),
                ('factura', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago', to='facturacion.factura')),
                ('proyecto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links_pago', to='proyectos.proyecto')),
            ],
            options={
                'verbose_name': 'link de pago',
                'verbose_name_plural': 'links de pago',
                'db_table': 'caja_link_pago',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='PagoRecibido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pasarela', models.CharField(choices=[('stripe', 'Stripe'), ('mercadopago', 'MercadoPago')], max_length=12)),
                ('id_externo', models.CharField(max_length=120)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('moneda', models.CharField(default='MXN', max_length=3)),
                ('fecha_pago', models.DateTimeField(blank=True, null=True)),
                ('estado', models.CharField(choices=[('registrado', 'Registrado'), ('por_revisar', 'Por revisar'), ('pendiente', 'Pendiente de acreditar'), ('rechazado', 'Rechazado'), ('descartado', 'Descartado')], db_index=True, max_length=12)),
                ('estado_pasarela', models.CharField(blank=True, default='', max_length=40)),
                ('motivo', models.CharField(blank=True, default='', max_length=300)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('revisado_en', models.DateTimeField(blank=True, null=True)),
                ('nota_revision', models.CharField(blank=True, default='', max_length=300)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('ingreso', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos_en_linea', to='tesoreria.ingreso')),
                ('link', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos', to='caja.linkpago')),
                ('revisado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos_en_linea_revisados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'pago recibido en línea',
                'verbose_name_plural': 'pagos recibidos en línea',
                'db_table': 'caja_pago_recibido',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='linkpago',
            index=models.Index(fields=['estado', '-creado_en'], name='caja_link_p_estado_9bff7e_idx'),
        ),
        migrations.AddIndex(
            model_name='linkpago',
            index=models.Index(fields=['factura', 'estado'], name='caja_link_p_factura_0f5d76_idx'),
        ),
        migrations.AddIndex(
            model_name='linkpago',
            index=models.Index(fields=['cotizacion', 'estado'], name='caja_link_p_cotizac_5c7d01_idx'),
        ),
        migrations.AddIndex(
            model_name='pagorecibido',
            index=models.Index(fields=['estado', '-creado_en'], name='caja_pago_r_estado_fcac7a_idx'),
        ),
        migrations.AddConstraint(
            model_name='pagorecibido',
            constraint=models.UniqueConstraint(fields=('pasarela', 'id_externo'), name='caja_pago_unico_por_pasarela'),
        ),
    ]
