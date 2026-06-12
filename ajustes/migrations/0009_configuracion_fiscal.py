from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0008_configuracion_cobranza'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionFiscal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('regimen', models.CharField(choices=[('resico_pf', 'RESICO · Persona Física'), ('resico_pm', 'RESICO · Persona Moral'), ('general_pm', 'General de Ley · Persona Moral'), ('pf_actividad', 'Persona Física con Actividad Empresarial'), ('rif', 'RIF (Régimen de Incorporación Fiscal)'), ('otro', 'Otro')], default='resico_pf', help_text='Régimen fiscal del despacho. Solo informativo + ayuda a elegir las tasas.', max_length=20)),
                ('isr_base', models.CharField(choices=[('ingresos', 'Sobre ingresos'), ('utilidad', 'Sobre la utilidad')], default='ingresos', help_text='Sobre qué se estima el ISR: ingresos (RESICO PF) o utilidad.', max_length=10)),
                ('isr_tasa', models.DecimalField(decimal_places=3, default=Decimal('2.000'), help_text='% para estimar el ISR. RESICO PF ronda 1–2.5%; régimen general 30%.', max_digits=6)),
                ('ptu_aplica', models.BooleanField(default=False, help_text='¿Se estima PTU? (normalmente no en RESICO PF sin empleados).')),
                ('ptu_tasa', models.DecimalField(decimal_places=3, default=Decimal('10.000'), help_text='% de PTU sobre la utilidad (estándar 10%).', max_digits=6)),
                ('iva_tasa', models.DecimalField(decimal_places=3, default=Decimal('16.000'), help_text='% de IVA aplicable (estándar 16% en México).', max_digits=6)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('actualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_fiscal_actualizadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'configuración fiscal',
                'verbose_name_plural': 'configuración fiscal',
                'db_table': 'ajustes_configuracion_fiscal',
            },
        ),
    ]
