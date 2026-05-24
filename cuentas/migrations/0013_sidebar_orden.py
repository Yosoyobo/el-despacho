"""S-LC-Feedback-V5 c6: tabla SidebarOrden + seed de defaults."""

from __future__ import annotations

from django.db import migrations, models

SEED = [
    ("dashboard", 10),
    ("clientes", 20),
    ("proyectos", 30),
    ("calendario", 40),
    ("buzon", 50),
    ("recados", 60),
    ("productos", 70),
    ("notificaciones", 80),
    ("chalanes", 90),
    ("cotizaciones", 100),
    ("finanzas", 110),
    ("ajustes", 120),
    ("ayuda", 130),
]


def seed(apps, schema_editor):
    SidebarOrden = apps.get_model("cuentas", "SidebarOrden")
    for slug, orden in SEED:
        SidebarOrden.objects.get_or_create(slug=slug, defaults={"orden": orden, "oculto": False})


def reverse(apps, schema_editor):
    apps.get_model("cuentas", "SidebarOrden").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0012_seed_permiso_gerencia")]
    operations = [
        migrations.CreateModel(
            name="SidebarOrden",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(db_index=True, max_length=40, unique=True)),
                ("orden", models.PositiveIntegerField(db_index=True, default=100)),
                ("oculto", models.BooleanField(default=False)),
            ],
            options={"db_table": "cuentas_sidebar_orden", "ordering": ["orden", "slug"]},
        ),
        migrations.RunPython(seed, reverse),
    ]
