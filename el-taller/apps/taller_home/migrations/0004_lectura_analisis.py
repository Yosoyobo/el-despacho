"""Guarda la lectura diaria de El Análisis.

Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("taller_home", "0003_meta_kpi"),
    ]

    operations = [
        migrations.CreateModel(
            name="LecturaAnalisis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("dominio", models.CharField(
                    db_index=True, max_length=20,
                    help_text="Tema del negocio (finanzas, cobranza, ventas…).")),
                ("texto", models.TextField(
                    help_text="Lo que opinó El Chalán sobre este tema.")),
                ("modelo_ia", models.CharField(blank=True, default="", max_length=80)),
                ("generado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "lectura de El Análisis",
                "verbose_name_plural": "lecturas de El Análisis",
                "db_table": "taller_home_lectura_analisis",
                "ordering": ["-generado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="lecturaanalisis",
            index=models.Index(fields=["dominio", "-generado_en"],
                               name="th_lectura_dom_fecha_idx"),
        ),
    ]
