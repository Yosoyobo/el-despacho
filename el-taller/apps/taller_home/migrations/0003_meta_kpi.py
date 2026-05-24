"""S-LC-Feedback-V5 c8: tabla MetaKPI."""

from __future__ import annotations

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taller_home", "0002_kpi_custom"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="MetaKPI",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kpi_slug", models.CharField(db_index=True, max_length=80, unique=True)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=14)),
                ("periodo", models.CharField(choices=[("mes", "Mensual"), ("trimestre", "Trimestral"), ("ano", "Anual")], default="mes", max_length=20)),
                ("activa", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="metas_kpi_modificadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "taller_home_meta_kpi", "ordering": ["kpi_slug"]},
        ),
    ]
