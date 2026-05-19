from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecadoGrupo",
            fields=[
                ("slug", models.CharField(max_length=50, primary_key=True, serialize=False)),
                ("nombre_legible", models.CharField(max_length=100)),
                ("descripcion", models.CharField(blank=True, default="", max_length=300)),
                ("tipo", models.CharField(choices=[("estatico", "Estático"), ("rol", "Por rol"), ("dinamico", "Dinámico")], max_length=20)),
                ("roles", models.JSONField(blank=True, default=list)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "recado_grupo", "ordering": ["slug"]},
        ),
        migrations.CreateModel(
            name="Recado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("cuerpo", models.TextField()),
                ("cuerpo_normalizado", models.TextField(blank=True, default="")),
                ("editado", models.BooleanField(default=False)),
                ("editado_en", models.DateTimeField(blank=True, null=True)),
                ("version_actual", models.IntegerField(default=1)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("autor", models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name="recados_enviados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "recado", "ordering": ["-creado_en"]},
        ),
        migrations.AddIndex(
            model_name="recado",
            index=models.Index(fields=["-creado_en"], name="recado_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="recado",
            index=models.Index(fields=["autor", "-creado_en"], name="recado_autor_creado_idx"),
        ),
        migrations.CreateModel(
            name="RecadoDestinatario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("leido_en", models.DateTimeField(blank=True, null=True)),
                ("recado", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="destinatarios", to="recados.recado")),
                ("usuario", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="recados_recibidos", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "recado_destinatario",
                "unique_together": {("recado", "usuario")},
            },
        ),
        migrations.AddIndex(
            model_name="recadodestinatario",
            index=models.Index(fields=["usuario", "-recado"], name="recado_dest_user_recado_idx"),
        ),
        migrations.AddIndex(
            model_name="recadodestinatario",
            index=models.Index(fields=["usuario", "leido_en"], name="recado_dest_user_leido_idx"),
        ),
        migrations.CreateModel(
            name="RecadoVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("version", models.IntegerField()),
                ("cuerpo", models.TextField()),
                ("editado_en", models.DateTimeField()),
                ("editado_por", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("recado", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="versiones", to="recados.recado")),
            ],
            options={
                "db_table": "recado_version",
                "ordering": ["recado", "version"],
                "unique_together": {("recado", "version")},
            },
        ),
    ]
