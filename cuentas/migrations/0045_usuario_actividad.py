"""Sprint de pendientes 2026-09-28: la última actividad de cada usuario.

Sólo ESQUEMA (§14 Bug I: una migración cambia el esquema o mueve datos, no las
dos cosas). El seed del permiso que decide quién la ve va en 0046.

Todos los campos nacen vacíos: nadie tiene «última actividad» hasta que vuelva a
entrar o a picar algo, y eso se muestra como «sin actividad registrada» — no como
desconectado hace mil años, que sería inventar un dato.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0044_seed_permisos_papeleo")]
    operations = [
        migrations.AddField(
            model_name="usuario",
            name="actividad_en",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_app",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_ruta",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_url_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_kwargs",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_accion",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="usuario",
            name="actividad_agente",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
    ]
