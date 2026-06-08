"""S-Directorio-Panel-V1: tabla PresupuestoIA (tope de gasto IA en USD por usuario)."""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0016_seed_permisos_chalan")]
    operations = [
        migrations.CreateModel(
            name="PresupuestoIA",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tope_usd", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("politica", models.CharField(choices=[("alertar", "Solo alertar"), ("topar", "Topar consumo")], default="alertar", max_length=10)),
                ("activo", models.BooleanField(default=True)),
                ("alerta_mes", models.CharField(blank=True, default="", max_length=7)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="presupuesto_ia", to="cuentas.usuario")),
                ("actualizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="presupuestos_ia_editados", to="cuentas.usuario")),
            ],
            options={
                "db_table": "cuentas_presupuesto_ia",
                "verbose_name": "presupuesto de IA",
                "verbose_name_plural": "presupuestos de IA",
            },
        ),
    ]
