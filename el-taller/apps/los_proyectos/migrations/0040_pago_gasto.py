# Oscar 2026-10-14: pagos PARCIALES de los gastos del proyecto (anticipo 50%, otro
# monto, sólo algunos conceptos). Tabla nueva, sin tocar datos.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0039_rename_proyectos_a_proyect_idx_proyectos_a_proyect_9cb150_idx_and_more'),
        ('tesoreria', '0009_egreso_origen_cfdi'),
    ]

    operations = [
        migrations.CreateModel(
            name='PagoGasto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('egreso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pagos_gasto', to='tesoreria.egreso')),
                ('proceso', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pagos_gasto', to='proyectos.proyectoproductoproceso')),
                ('producto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pagos_gasto', to='proyectos.proyectoproducto')),
            ],
            options={
                'db_table': 'proyectos_pago_gasto',
                'ordering': ['pk'],
                'constraints': [
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(('producto__isnull', False), ('proceso__isnull', True)),
                            models.Q(('producto__isnull', True), ('proceso__isnull', False)),
                            _connector='OR',
                        ),
                        name='pago_gasto_un_solo_gasto',
                    ),
                ],
            },
        ),
    ]
