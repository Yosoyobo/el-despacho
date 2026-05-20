from decimal import Decimal

import apps.cotizaciones.models.cotizacion as _cotmod
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ajustes", "0002_tasa_impositiva"),
        ("cartera", "0002_cliente_slug"),
        ("proyectos", "0003_proyecto_slug"),
        ("el_catalogo", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Cotizacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=20, unique=True)),
                ("titulo", models.CharField(max_length=200)),
                ("estado", models.CharField(
                    choices=[
                        ("borrador", "Borrador"),
                        ("enviada", "Enviada"),
                        ("aprobada", "Aprobada"),
                        ("rechazada", "Rechazada"),
                        ("anulada", "Anulada"),
                    ],
                    db_index=True, default="borrador", max_length=20)),
                ("fecha_emision", models.DateField(default=_cotmod.date.today)),
                ("fecha_validez", models.DateField(default=_cotmod._validez_default)),
                ("moneda", models.CharField(default="MXN", max_length=3)),
                ("descuento_global_porcentaje", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("notas", models.TextField(blank=True, default="")),
                ("terminos", models.TextField(blank=True, default="")),
                ("enviada_en", models.DateTimeField(blank=True, null=True)),
                ("enviada_a_email", models.CharField(blank=True, default="", max_length=200)),
                ("aprobada_en", models.DateTimeField(blank=True, null=True)),
                ("aprobada_por_nombre", models.CharField(blank=True, default="", max_length=200)),
                ("aprobada_por_email", models.CharField(blank=True, default="", max_length=200)),
                ("referencia_aprobacion", models.CharField(blank=True, default="", max_length=200)),
                ("rechazada_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_rechazo", models.TextField(blank=True, default="")),
                ("anulada_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_anulacion", models.CharField(blank=True, default="", max_length=300)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("anulada_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cotizaciones_anuladas", to=settings.AUTH_USER_MODEL)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cotizaciones", to="cartera.cliente")),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cotizaciones_creadas", to=settings.AUTH_USER_MODEL)),
                ("proyecto", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cotizaciones", to="proyectos.proyecto")),
            ],
            options={
                "db_table": "cotizaciones_cotizacion",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="cotizacion",
            index=models.Index(fields=["cliente", "-creado_en"], name="cotiz_cliente_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="cotizacion",
            index=models.Index(fields=["proyecto", "-creado_en"], name="cotiz_proyecto_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="cotizacion",
            index=models.Index(fields=["estado", "-fecha_emision"], name="cotiz_estado_fecha_idx"),
        ),
        migrations.CreateModel(
            name="CotizacionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(db_index=True, default=0)),
                ("descripcion", models.TextField()),
                ("cantidad", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=12)),
                ("unidad", models.CharField(default="pieza", max_length=30)),
                ("precio_unitario", models.DecimalField(decimal_places=2, max_digits=12)),
                ("descuento_porcentaje", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("cotizacion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="cotizaciones.cotizacion")),
                ("servicio", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lineas_cotizacion", to="el_catalogo.servicio")),
            ],
            options={
                "db_table": "cotizaciones_item",
                "ordering": ["cotizacion", "orden", "pk"],
            },
        ),
        migrations.CreateModel(
            name="CotizacionImpuesto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("aplicado_en", models.DateTimeField(auto_now_add=True)),
                ("cotizacion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="impuestos", to="cotizaciones.cotizacion")),
                ("tasa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cotizaciones", to="ajustes.tasaimpositiva")),
            ],
            options={
                "db_table": "cotizaciones_impuesto",
                "ordering": ["tasa__orden", "tasa__nombre"],
                "unique_together": {("cotizacion", "tasa")},
            },
        ),
    ]
