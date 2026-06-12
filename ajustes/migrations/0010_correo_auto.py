"""S-LC-Feedback-V6 Bloque 7A: flags de correos automáticos en la
configuración de El Cartero (bienvenida al alta de cliente + confirmación de
pago). Arrancan APAGADOS."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ajustes", "0009_configuracion_fiscal"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracioncorreo",
            name="auto_bienvenida",
            field=models.BooleanField(
                default=False,
                help_text="Enviar correo de bienvenida al dar de alta un cliente con email.",
            ),
        ),
        migrations.AddField(
            model_name="configuracioncorreo",
            name="auto_pago",
            field=models.BooleanField(
                default=False,
                help_text="Enviar confirmación de pago al registrar un ingreso con cliente.",
            ),
        ),
    ]
