"""La memoria de los indicadores: una foto diaria por KPI.

Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("taller_home", "0004_lectura_analisis"),
    ]

    operations = [
        migrations.CreateModel(
            name="SnapshotKPI",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("kpi_slug", models.CharField(db_index=True, max_length=80)),
                ("fecha", models.DateField(db_index=True)),
                ("valor", models.DecimalField(
                    decimal_places=4, max_digits=16,
                    help_text="El número del indicador ese día.")),
                ("nota", models.CharField(blank=True, default="", max_length=200)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "foto diaria de indicador",
                "verbose_name_plural": "fotos diarias de indicadores",
                "db_table": "taller_home_snapshot_kpi",
                "ordering": ["-fecha", "kpi_slug"],
            },
        ),
        migrations.AddConstraint(
            model_name="snapshotkpi",
            constraint=models.UniqueConstraint(
                fields=("kpi_slug", "fecha"), name="uniq_snapshot_kpi_dia",
            ),
        ),
        migrations.AddIndex(
            model_name="snapshotkpi",
            index=models.Index(fields=["kpi_slug", "-fecha"], name="th_snap_kpi_fecha_idx"),
        ),
    ]
