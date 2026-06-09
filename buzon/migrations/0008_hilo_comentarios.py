"""S-LC-Buzon-V2 (C5d): hilo de comentarios autor↔admin + singleton de config."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buzon", "0007_estado_accion_estado_manual"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionBuzon",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("empleado_puede_responder", models.BooleanField(
                    default=False,
                    help_text="Si está activo, el autor del mensaje puede responder en su propio ticket.")),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "buzon_configuracion",
                "verbose_name": "configuración del Buzón",
                "verbose_name_plural": "configuración del Buzón",
            },
        ),
        migrations.CreateModel(
            name="MensajeBuzonComentario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cuerpo", models.TextField()),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("autor", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="comentarios_buzon", to=settings.AUTH_USER_MODEL)),
                ("mensaje", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comentarios", to="buzon.mensajebuzon")),
            ],
            options={
                "db_table": "buzon_comentario",
                "ordering": ["creado_en"],
                "indexes": [models.Index(fields=["mensaje", "creado_en"], name="buzon_comen_mensaje_idx")],
            },
        ),
    ]
