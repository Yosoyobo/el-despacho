"""Hotfix SSO (alcance Interfono): URLFields → TextField.

Política nueva: URLs no se benefician de max_length arbitrario; usar
TextField. Documentado en cierre de SSO en BITACORA.md.

- InterfonoEnvio.url_destino: URLField (default 200) → TextField
- InterfonoSuscripcion.endpoint: URLField(max_length=2000, unique) →
  TextField(unique). Postgres soporta UNIQUE sobre TEXT sin overhead.

Solo AlterField. Cero RunPython. No-destructiva.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interfono", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="interfonoenvio",
            name="url_destino",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="interfonosuscripcion",
            name="endpoint",
            field=models.TextField(unique=True),
        ),
    ]
