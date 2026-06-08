"""S-Estados-Color-HEX: color HEX libre para las categorías de servicio."""

from __future__ import annotations

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("el_catalogo", "0005_proveedor")]

    operations = [
        migrations.AddField(
            model_name="categoriaservicio",
            name="color",
            field=models.CharField(
                default="#667085",
                help_text="Color HEX del badge, ej. #465fff.",
                max_length=7,
                validators=[django.core.validators.RegexValidator(
                    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
                    regex=r"^#[0-9a-fA-F]{6}$",
                )],
            ),
        ),
    ]
