"""S-Checador-V2 — la nómina interna quincenal (sólo esquema; Bug I).

Sueldo por persona con vigencia, quincenas, recibos, conceptos y préstamos.
La siembra del permiso `nomina` va aparte, en `0010_seed_permisos_nomina`.
"""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checador', '0008_poi_visita_sede_geo'),
        ('tesoreria', '0009_egreso_origen_cfdi'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PeriodoNomina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_inicio', models.DateField(unique=True)),
                ('fecha_fin', models.DateField()),
                ('estado', models.CharField(choices=[('abierto', 'Abierto'), ('calculado', 'Calculado'), ('cerrado', 'Cerrado')], default='abierto', max_length=10)),
                ('notas', models.TextField(blank=True, default='')),
                ('calculado_en', models.DateTimeField(blank=True, null=True)),
                ('cerrado_en', models.DateTimeField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('calculado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='periodos_nomina_calculados', to=settings.AUTH_USER_MODEL)),
                ('cerrado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='periodos_nomina_cerrados', to=settings.AUTH_USER_MODEL)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='periodos_nomina_creados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'checador_periodo_nomina',
                'ordering': ['-fecha_inicio'],
            },
        ),
        migrations.CreateModel(
            name='PrestamoNomina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('concepto', models.CharField(default='Préstamo', max_length=160)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('fecha', models.DateField()),
                ('cuota', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('quincenas', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('saldo', models.DecimalField(decimal_places=2, max_digits=12)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prestamos_nomina_capturados', to=settings.AUTH_USER_MODEL)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='prestamos_nomina', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'checador_prestamo_nomina',
                'ordering': ['-fecha', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ReciboNomina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sueldo_aplicado', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('sueldo_vigente_desde', models.DateField(blank=True, null=True)),
                ('sueldo_anterior', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('dias_laborales', models.PositiveSmallIntegerField(default=0)),
                ('horas_esperadas', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=7)),
                ('horas_trabajadas', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=7)),
                ('retardos', models.PositiveSmallIntegerField(default=0)),
                ('minutos_retardo', models.PositiveIntegerField(default=0)),
                ('faltas', models.PositiveSmallIntegerField(default=0)),
                ('percepciones', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('deducciones', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('neto', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('estado', models.CharField(choices=[('por_pagar', 'Por pagar'), ('pagado', 'Pagado')], default='por_pagar', max_length=10)),
                ('pagado_en', models.DateField(blank=True, help_text='Fecha real del depósito.', null=True)),
                ('pago_registrado_en', models.DateTimeField(blank=True, null=True)),
                ('metodo_pago', models.CharField(blank=True, default='', max_length=30)),
                ('quitados', models.JSONField(blank=True, default=list)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('pagado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recibos_nomina_marcados', to=settings.AUTH_USER_MODEL)),
                ('periodo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recibos', to='checador.periodonomina')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recibos_nomina', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'checador_recibo_nomina',
                'ordering': ['periodo_id', 'usuario__nombre_completo'],
            },
        ),
        migrations.CreateModel(
            name='ConceptoRecibo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('percepcion', 'Percepción'), ('deduccion', 'Deducción')], max_length=10)),
                ('clase', models.CharField(choices=[('bono', 'Bono / comisión'), ('prestamo', 'Abono a préstamo'), ('reembolso', 'Reembolso'), ('deduccion', 'Deducción'), ('ajuste', 'Ajuste')], max_length=10)),
                ('descripcion', models.CharField(max_length=200)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('nota', models.TextField(blank=True, default='')),
                ('automatico', models.BooleanField(default=False)),
                ('orden', models.PositiveSmallIntegerField(default=100)),
                ('egreso', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conceptos_nomina', to='tesoreria.egreso')),
                ('prestamo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='abonos', to='checador.prestamonomina')),
                ('recibo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conceptos', to='checador.recibonomina')),
            ],
            options={
                'db_table': 'checador_concepto_recibo',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SueldoPersona',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sueldo_quincenal', models.DecimalField(decimal_places=2, help_text='Lo que cobra por quincena, antes de conceptos.', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('vigente_desde', models.DateField(help_text='Desde qué día aplica. Lo más claro es el 1 o el 16.')),
                ('en_nomina', models.BooleanField(default=True, help_text='Apagado = baja: desde esta fecha la persona ya no cobra por nómina.')),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sueldos_nomina_capturados', to=settings.AUTH_USER_MODEL)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sueldos_nomina', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'checador_sueldo_persona',
                'ordering': ['usuario_id', '-vigente_desde'],
            },
        ),
        migrations.AddConstraint(
            model_name='recibonomina',
            constraint=models.UniqueConstraint(fields=('periodo', 'usuario'), name='checador_recibo_periodo_usuario'),
        ),
        migrations.AddConstraint(
            model_name='sueldopersona',
            constraint=models.UniqueConstraint(fields=('usuario', 'vigente_desde'), name='checador_sueldo_usuario_desde'),
        ),
    ]
