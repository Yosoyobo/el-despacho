"""S-LC-Feedback-V3: CRM de Proveedores + M2M con Servicio."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0004_costo_servicio"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Proveedor",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("razon_social", models.CharField(max_length=200, db_index=True)),
                ("nombre_contacto", models.CharField(max_length=120, blank=True, default="")),
                ("email_contacto", models.EmailField(blank=True, default="", max_length=254)),
                ("telefono", models.CharField(max_length=40, blank=True, default="")),
                ("rfc", models.CharField(max_length=20, blank=True, default="")),
                ("direccion", models.TextField(blank=True, default="")),
                ("notas", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True, db_index=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="proveedores_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "catalogo_proveedor",
                "ordering": ["razon_social"],
                "verbose_name": "proveedor",
                "verbose_name_plural": "proveedores",
            },
        ),
        migrations.AddField(
            model_name="servicio",
            name="proveedores",
            field=models.ManyToManyField(
                blank=True,
                related_name="servicios",
                to="el_catalogo.proveedor",
            ),
        ),
    ]
