import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed(apps, schema_editor):
    PlantillaCorreo = apps.get_model("ajustes", "PlantillaCorreo")
    from ajustes.plantillas_correo_default import PLANTILLAS_DEFAULT, SLUGS_PLANTILLA
    for slug in SLUGS_PLANTILLA:
        d = PLANTILLAS_DEFAULT[slug]
        PlantillaCorreo.objects.get_or_create(slug=slug, defaults={
            "nombre": d["nombre"], "asunto": d["asunto"],
            "cuerpo_html": d["cuerpo_html"],
        })


def unseed(apps, schema_editor):
    apps.get_model("ajustes", "PlantillaCorreo").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ajustes", "0006_configuracion_correo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlantillaCorreo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(db_index=True, max_length=40, unique=True)),
                ("nombre", models.CharField(max_length=120)),
                ("asunto", models.CharField(blank=True, default="", max_length=300)),
                ("cuerpo_html", models.TextField(blank=True, default="")),
                ("activa", models.BooleanField(default=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="plantillas_correo_actualizadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "plantilla de correo",
                "verbose_name_plural": "plantillas de correo",
                "db_table": "ajustes_plantilla_correo",
                "ordering": ["slug"],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
