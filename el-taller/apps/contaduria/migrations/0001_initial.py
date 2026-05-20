from decimal import Decimal

import apps.contaduria.models.asiento as _ast
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CuentaContable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=20, unique=True)),
                ("nombre", models.CharField(max_length=120)),
                ("tipo", models.CharField(
                    choices=[
                        ("activo", "Activo"), ("pasivo", "Pasivo"),
                        ("capital", "Capital"), ("ingreso", "Ingreso"),
                        ("egreso", "Egreso"),
                    ],
                    db_index=True, max_length=20)),
                ("naturaleza", models.CharField(
                    choices=[("deudora", "Deudora"), ("acreedora", "Acreedora")],
                    max_length=20)),
                ("descripcion", models.CharField(blank=True, default="", max_length=300)),
                ("slot", models.CharField(blank=True, db_index=True, default="", max_length=40)),
                ("activa", models.BooleanField(db_index=True, default=True)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("actualizada_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "contaduria_cuenta_contable",
                "ordering": ["codigo"],
            },
        ),
        migrations.CreateModel(
            name="Asiento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=20, unique=True)),
                ("fecha", models.DateField(db_index=True, default=_ast.date.today)),
                ("descripcion", models.CharField(max_length=300)),
                ("origen", models.CharField(
                    choices=[
                        ("manual", "Captura manual"),
                        ("auto_ingreso", "Automático · ingreso Tesorería"),
                        ("auto_egreso", "Automático · egreso Tesorería"),
                        ("auto_anulacion_ingreso", "Automático · anulación ingreso"),
                        ("auto_anulacion_egreso", "Automático · anulación egreso"),
                        ("ajuste", "Ajuste contable"),
                        ("cierre", "Cierre de periodo"),
                    ],
                    db_index=True, default="manual", max_length=30)),
                ("referencia_externa", models.CharField(blank=True, db_index=True, default="", max_length=120)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("anulado", models.BooleanField(db_index=True, default=False)),
                ("anulado_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_anulacion", models.CharField(blank=True, default="", max_length=300)),
                ("anulado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="asientos_anulados", to=settings.AUTH_USER_MODEL)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="asientos_creados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "contaduria_asiento",
                "ordering": ["-fecha", "-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="asiento",
            index=models.Index(fields=["-fecha", "-creado_en"], name="ctd_asiento_fc_idx"),
        ),
        migrations.AddIndex(
            model_name="asiento",
            index=models.Index(fields=["origen", "-fecha"], name="ctd_asiento_orig_idx"),
        ),
        migrations.CreateModel(
            name="Partida",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("cargo", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("abono", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("descripcion", models.CharField(blank=True, default="", max_length=200)),
                ("asiento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="partidas", to="contaduria.asiento")),
                ("cuenta", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partidas", to="contaduria.cuentacontable")),
            ],
            options={
                "db_table": "contaduria_partida",
                "ordering": ["asiento", "orden", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="partida",
            constraint=models.CheckConstraint(
                condition=models.Q(cargo__gte=0) & models.Q(abono__gte=0),
                name="contaduria_partida_montos_no_negativos",
            ),
        ),
        migrations.AddIndex(
            model_name="partida",
            index=models.Index(fields=["cuenta"], name="ctd_partida_cuenta_idx"),
        ),
    ]
