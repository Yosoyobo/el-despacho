"""Canal nuevo de El Cartero: Gmail API por HTTPS.

Sólo `AlterField` de los choices — no toca datos. Existe porque el Droplet tiene
bloqueada la salida SMTP (DigitalOcean descarta 25/465/587/2525) y la API de
Gmail va por 443.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0013_ret_iva_honorarios_tasa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="configuracioncorreo",
            name="proveedor",
            field=models.CharField(
                choices=[
                    ("n8n", "n8n (vía El Portavoz)"),
                    ("smtp", "SMTP directo"),
                    ("gmail_api", "Gmail API (Google Workspace)"),
                ],
                default="n8n",
                max_length=10,
            ),
        ),
    ]
