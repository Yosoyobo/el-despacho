"""Campos para el resultado del último 'Probar conexión' en Credencial.

Aplica primariamente a slots de IA (`chalan_*_api_key`) — los demás slots
nunca tendrán test. El UI de Los Chalanes muestra `ultimo_test_ok` con su
fecha relativa; el chequeo diario de El Site también los actualiza.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0004_chalanes_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="credencial",
            name="ultimo_test_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="credencial",
            name="ultimo_test_ok",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="credencial",
            name="ultimo_test_mensaje",
            field=models.CharField(blank=True, default="", max_length=240),
        ),
    ]
