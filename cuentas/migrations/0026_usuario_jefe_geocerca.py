"""S-LC-Feedback-V7 — jefe directo + dirección/pin/geocerca en el perfil."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0025_sidebar_orden_usuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="jefe_directo",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="subordinados", to="cuentas.usuario",
                help_text="Aprueba los ajustes de horas de este empleado."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="direccion",
            field=models.TextField(blank=True, default="", help_text="Dirección del empleado (texto libre)."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="geo_lat",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="geo_lng",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="geocerca_radio_m",
            field=models.PositiveIntegerField(default=150, help_text="Radio de la geocerca en metros."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="geocerca_activa",
            field=models.BooleanField(default=False, help_text="Activa la validación de geocerca para este empleado."),
        ),
    ]
