# S-LC-Proyecto-Render-V1: proveedor principal por producto + procesos
# (impresión ligada a proveedor + gastos operativos sin proveedor).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0011_iva_e_incluir_calculo'),
        ('el_catalogo', '0005_proveedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyectoproducto',
            name='proveedor',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='productos_proyecto',
                to='el_catalogo.proveedor',
            ),
        ),
        migrations.CreateModel(
            name='ProyectoProductoProceso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('impresion', 'Impresión'), ('operativo', 'Gasto operativo')], default='operativo', max_length=16)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
                ('descripcion', models.CharField(blank=True, default='', max_length=200)),
                ('costo', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='procesos', to='proyectos.proyectoproducto')),
                ('proveedor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='procesos_proyecto', to='el_catalogo.proveedor')),
            ],
            options={
                'verbose_name': 'proceso del producto',
                'verbose_name_plural': 'procesos del producto',
                'db_table': 'proyectos_producto_proceso',
                'ordering': ['orden', 'creado_en'],
            },
        ),
    ]
