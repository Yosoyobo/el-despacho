from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contaduria', '0003_origenes_factura'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asiento',
            name='origen',
            field=models.CharField(
                choices=[
                    ('manual', 'Captura manual'),
                    ('auto_ingreso', 'Automático · ingreso Tesorería'),
                    ('auto_egreso', 'Automático · egreso Tesorería'),
                    ('auto_anulacion_ingreso', 'Automático · anulación ingreso'),
                    ('auto_anulacion_egreso', 'Automático · anulación egreso'),
                    ('auto_factura_emitida', 'Automático · factura emitida'),
                    ('auto_factura_cancelada', 'Automático · factura cancelada'),
                    ('auto_reembolso', 'Automático · reembolso a empleado'),
                    ('ajuste', 'Ajuste contable'),
                    ('cierre', 'Cierre de periodo'),
                ],
                db_index=True, default='manual', max_length=30,
            ),
        ),
    ]
