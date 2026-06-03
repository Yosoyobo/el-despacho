# C5 S-LC-Feedback-V6 — Proveedores asignados a un proyecto.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('el_catalogo', '0005_proveedor'),
        ('proyectos', '0009_producto_precio_costo_merma'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProyectoProveedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('entregan_ellos', 'Ellos nos entregan'), ('recogemos_nosotros', 'Nosotros recogemos')], default='entregan_ellos', max_length=24)),
                ('compromiso', models.DateTimeField(blank=True, help_text='Cuándo se comprometen a entregar o cuándo hay que recoger.', null=True)),
                ('contacto', models.CharField(blank=True, default='', max_length=160)),
                ('ubicacion', models.CharField(blank=True, default='', max_length=300)),
                ('nota', models.CharField(blank=True, default='', max_length=300)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('proveedor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='proyectos_asignados', to='el_catalogo.proveedor')),
                ('proyecto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proveedores_asignados', to='proyectos.proyecto')),
            ],
            options={
                'verbose_name': 'proveedor del proyecto',
                'verbose_name_plural': 'proveedores del proyecto',
                'db_table': 'proyectos_proveedor',
                'ordering': ['compromiso', 'creado_en'],
            },
        ),
    ]
