"""Modelo ConocimientoNegocio (S-Chalan-Negocio-V1).

Observaciones durables del negocio que el Chalán destila (review-first) y que
fundamentan sus opiniones. Tabla nueva; no toca nada existente.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_dictado", "0006_aprendizaje_origen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConocimientoNegocio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ambito", models.CharField(choices=[("finanzas", "Económicos / Finanzas"), ("cobranza", "Cobranza"), ("ventas", "Ventas"), ("margenes", "Costos y márgenes")], db_index=True, max_length=20)),
                ("observacion", models.CharField(max_length=400)),
                ("evidencia", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=False)),
                ("peso", models.FloatField(default=1.0)),
                ("origen", models.CharField(choices=[("manual", "Capturado a mano"), ("chalan_destilado", "Destilado por el Chalán")], default="chalan_destilado", max_length=20)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("desactivado_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_desactivacion", models.CharField(blank=True, default="", max_length=200)),
                ("autor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conocimientos_negocio", to=settings.AUTH_USER_MODEL)),
                ("desactivado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conocimientos_negocio_desactivados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "el_dictado_conocimiento_negocio",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="conocimientonegocio",
            index=models.Index(fields=["activo", "ambito"], name="el_dictado__activo_5b8e4f_idx"),
        ),
        migrations.AddIndex(
            model_name="conocimientonegocio",
            index=models.Index(fields=["-creado_en"], name="el_dictado__creado__a1c2d3_idx"),
        ),
    ]
