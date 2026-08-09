"""S-Celador-V1: bitácora de intentos de acceso (alimenta `uso` en /salud)."""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0039_seed_permiso_cotizaciones_eliminar")]
    operations = [
        migrations.CreateModel(
            name="IntentoAcceso",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app", models.CharField(choices=[("taller", "El Taller"), ("gerencia", "La Gerencia"), ("recepcion", "La Recepción")], max_length=20)),
                ("via", models.CharField(choices=[("password", "Email y contraseña"), ("google", "Google")], default="password", max_length=20)),
                ("email_intentado", models.CharField(blank=True, default="", max_length=254)),
                ("exito", models.BooleanField(default=False)),
                ("motivo", models.CharField(choices=[("ok", "Entró"), ("credenciales", "Credenciales inválidas"), ("faltan_datos", "Faltó email o contraseña"), ("sin_permiso", "Sin permiso para esta app"), ("limite", "Frenado por el límite de intentos"), ("sso", "Falló el acceso con Google")], default="credenciales", max_length=20)),
                ("ip", models.CharField(blank=True, default="", max_length=64)),
                ("agente", models.CharField(blank=True, default="", max_length=300)),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="intentos_acceso", to="cuentas.usuario")),
            ],
            options={
                "db_table": "cuentas_intento_acceso",
                "ordering": ["-creado_en"],
                "verbose_name": "intento de acceso",
                "verbose_name_plural": "intentos de acceso",
            },
        ),
        migrations.AddIndex(
            model_name="intentoacceso",
            index=models.Index(fields=["exito", "creado_en"], name="idx_intento_exito_fecha"),
        ),
    ]
