from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Usuario",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False)),
                ("email", models.EmailField(db_index=True, max_length=254, unique=True)),
                ("nombre_completo", models.CharField(max_length=200)),
                (
                    "rol",
                    models.CharField(
                        choices=[
                            ("super_admin", "Super Admin"),
                            ("dueno", "Dueño"),
                            ("contador", "Contador"),
                            ("disenador", "Diseñador"),
                        ],
                        db_index=True,
                        default="disenador",
                        max_length=20,
                    ),
                ),
                ("google_sub", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("avatar_url", models.URLField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("ultimo_acceso_en", models.DateTimeField(blank=True, null=True)),
                ("groups", models.ManyToManyField(blank=True, related_name="usuario_set", to="auth.group")),
                ("user_permissions", models.ManyToManyField(blank=True, related_name="usuario_set", to="auth.permission")),
            ],
            options={
                "verbose_name": "usuario",
                "verbose_name_plural": "usuarios",
                "db_table": "cuentas_usuario",
                "ordering": ["nombre_completo"],
            },
            managers=[],
        ),
    ]
