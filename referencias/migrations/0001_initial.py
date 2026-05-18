from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cuentas", "0005_usuario_slug"),
        ("cartera", "0002_cliente_slug"),
        ("proyectos", "0003_proyecto_slug"),
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
                ("token_original", models.CharField(max_length=200)),
                ("posicion_inicio", models.IntegerField()),
                ("posicion_fin", models.IntegerField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("cliente", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="referencias_recibidas", to="cartera.cliente",
                )),
                ("proyecto", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="referencias_recibidas", to="proyectos.proyecto",
                )),
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
        migrations.AddIndex(
            model_name="referencia",
            index=models.Index(fields=["tipo", "usuario"], name="ref_tipo_usr_idx"),
        ),
        migrations.AddIndex(
            model_name="referencia",
            index=models.Index(fields=["tipo", "proyecto"], name="ref_tipo_proy_idx"),
        ),
        migrations.AddIndex(
            model_name="referencia",
            index=models.Index(fields=["tipo", "cliente"], name="ref_tipo_cli_idx"),
        ),
        migrations.AddConstraint(
            model_name="referencia",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(tipo="usuario") & models.Q(usuario__isnull=False)
                        & models.Q(proyecto__isnull=True) & models.Q(cliente__isnull=True))
                    | (models.Q(tipo="proyecto") & models.Q(proyecto__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(cliente__isnull=True))
                    | (models.Q(tipo="cliente") & models.Q(cliente__isnull=False)
                        & models.Q(usuario__isnull=True) & models.Q(proyecto__isnull=True))
                ),
                name="referencia_tipo_fk_unica",
            ),
        ),
    ]
