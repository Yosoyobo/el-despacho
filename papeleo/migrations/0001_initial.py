"""S-Papeleo-V1: el puente entre un documento de Paperless y de quién es.

Sólo esquema. Los constraints son la garantía de verdad: «una sola entidad» y
«no dos veces la misma liga» las cuida la base, no una promesa del código.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cartera", "0008_razones_sociales"),
        ("proyectos", "0037_recolorear_tarjetas"),
        ("el_catalogo", "0014_servicio_proveedor_principal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PapeleoLigado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("documento_id", models.PositiveIntegerField(
                    help_text="El id que le dio Paperless al documento.")),
                ("titulo", models.CharField(
                    blank=True, default="", max_length=200,
                    help_text="Copia del título al ligarlo, para que la fila siga legible "
                              "si el documento desaparece del archivo.")),
                ("automatico", models.BooleanField(
                    default=False,
                    help_text="La ligó la regla al entrar el documento, no una persona.")),
                ("ligado_en", models.DateTimeField(auto_now_add=True)),
                ("cliente", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="papeleo", to="cartera.cliente")),
                ("proyecto", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="papeleo", to="proyectos.proyecto")),
                ("proveedor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="papeleo", to="el_catalogo.proveedor")),
                ("ligado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="papeleo_ligado", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "papeleo_ligado",
                "ordering": ["-ligado_en"],
                "verbose_name": "papeleo ligado",
                "verbose_name_plural": "papeleo ligado",
            },
        ),
        migrations.AddIndex(
            model_name="papeleoligado",
            index=models.Index(fields=["documento_id"],
                               name="papeleo_lig_documen_6250e3_idx"),
        ),
        migrations.AddConstraint(
            model_name="papeleoligado",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cliente__isnull=False, proyecto__isnull=True,
                             proveedor__isnull=True)
                    | models.Q(cliente__isnull=True, proyecto__isnull=False,
                               proveedor__isnull=True)
                    | models.Q(cliente__isnull=True, proyecto__isnull=True,
                               proveedor__isnull=False)
                ),
                name="papeleo_una_sola_entidad",
            ),
        ),
        migrations.AddConstraint(
            model_name="papeleoligado",
            constraint=models.UniqueConstraint(
                condition=models.Q(cliente__isnull=False),
                fields=("documento_id", "cliente"), name="papeleo_unico_cliente"),
        ),
        migrations.AddConstraint(
            model_name="papeleoligado",
            constraint=models.UniqueConstraint(
                condition=models.Q(proyecto__isnull=False),
                fields=("documento_id", "proyecto"), name="papeleo_unico_proyecto"),
        ),
        migrations.AddConstraint(
            model_name="papeleoligado",
            constraint=models.UniqueConstraint(
                condition=models.Q(proveedor__isnull=False),
                fields=("documento_id", "proveedor"), name="papeleo_unico_proveedor"),
        ),
    ]
