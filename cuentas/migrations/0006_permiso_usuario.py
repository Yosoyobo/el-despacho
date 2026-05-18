"""Pre-S2b.1: tabla PermisoUsuario granular."""

from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0005_usuario_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="PermisoUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("modulo", models.CharField(db_index=True, max_length=40)),
                ("permiso", models.CharField(db_index=True, max_length=60)),
                ("activo", models.BooleanField(default=True)),
                ("modificado_en", models.DateTimeField(auto_now=True)),
                ("modificado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="permisos_modificados", to=settings.AUTH_USER_MODEL,
                )),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="permisos_granulares", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "cuentas_permiso_usuario",
                "ordering": ["usuario_id", "modulo", "permiso"],
            },
        ),
        migrations.AddConstraint(
            model_name="permisousuario",
            constraint=models.UniqueConstraint(
                fields=("usuario", "modulo", "permiso"), name="permiso_usuario_unico"
            ),
        ),
    ]
