from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        # cuentas es shared (raíz), disponible en los 3 Django projects.
        # NO depender de cartera/proyectos (viven en El Taller y no están
        # en INSTALLED_APPS de La Gerencia) — proyecto_id y cliente_id son
        # BigIntegerField sin FK formal.
        ("cuentas", "0005_usuario_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="Referencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("contenedor_tipo", models.CharField(max_length=30, db_index=True)),
                ("contenedor_id", models.BigIntegerField(db_index=True)),
                ("tipo", models.CharField(
                    choices=[("usuario", "Usuario"), ("proyecto", "Proyecto"), ("cliente", "Cliente")],
                    db_index=True, max_length=10,
                )),
                ("proyecto_id", models.BigIntegerField(blank=True, null=True, db_index=True)),
                ("cliente_id", models.BigIntegerField(blank=True, null=True, db_index=True)),
                ("token_original", models.CharField(max_length=200)),
                ("posicion_inicio", models.IntegerField()),
                ("posicion_fin", models.IntegerField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("usuario", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="referencias_recibidas", to="cuentas.usuario",
                )),
            ],
            options={"db_table": "referencias_referencia"},
        ),
        migrations.AddIndex(
            model_name="referencia",
            index=models.Index(fields=["contenedor_tipo", "contenedor_id"], name="ref_contenedor_idx"),
        ),
        migrations.AddConstraint(
            model_name="referencia",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(tipo="usuario") & models.Q(usuario__isnull=False)
                        & models.Q(proyecto_id__isnull=True) & models.Q(cliente_id__isnull=True))
                    | (models.Q(tipo="proyecto") & models.Q(proyecto_id__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(cliente_id__isnull=True))
                    | (models.Q(tipo="cliente") & models.Q(cliente_id__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(proyecto_id__isnull=True))
                ),
                name="referencia_tipo_fk_unica",
            ),
        ),
    ]
